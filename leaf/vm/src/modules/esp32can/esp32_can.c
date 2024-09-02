/* The MIT License (MIT)
 *
 * Copyright (c) 2019 Musumeci Salvatore
 * Copyright (c) 2021 Ihor Nehrutsa
 * Copyright (c) 2022 Yuriy Makarov
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#if MICROPY_HW_ENABLE_CAN

#include <string.h>

#include "py/objarray.h"
#include "py/binary.h"
#include "py/runtime.h"
#include "py/mphal.h"
#include "py/mperrno.h"
#include "freertos/task.h"
#include "esp_idf_version.h"

#include "driver/twai.h"
#include "esp_task.h"
#include "esp32_can.h"

// TWAI_MODE_NORMAL      - Normal operating mode where TWAI controller can send/receive/acknowledge messages
// TWAI_MODE_NO_ACK      - Transmission does not require acknowledgment. Use this mode for self testing. // This mode is useful when self testing the TWAI controller (loopback of transmissions).
// TWAI_MODE_LISTEN_ONLY - The TWAI controller will not influence the bus (No transmissions or acknowledgments) but can receive messages. // This mode is suited for bus monitor applications.

#define CAN_MODE_NORMAL             TWAI_MODE_NORMAL
#define CAN_MODE_LOOPBACK           TWAI_MODE_NO_ACK
#define CAN_MODE_SILENT             TWAI_MODE_LISTEN_ONLY
#define CAN_MODE_SILENT_LOOPBACK    (0x10)

#define CAN_TASK_PRIORITY           (ESP_TASK_PRIO_MIN + 1)
#define CAN_TASK_STACK_SIZE         (1024)
#define CAN_DEFAULT_PRESCALER       (8)
#define CAN_DEFAULT_SJW             (3)
#define CAN_DEFAULT_BS1             (15)
#define CAN_DEFAULT_BS2             (4)
#define CAN_MAX_DATA_FRAME          (8)

// INTERNAL Deinitialize can
void can_deinit(const esp32_can_obj_t *self) {
    check_esp_err(twai_stop());
    check_esp_err(twai_driver_uninstall());
    if (self->irq_handler != NULL) {
        vTaskDelete(self->irq_handler);
    }
    self->config->initialized = false;
}

// singleton CAN device object
esp32_can_config_t can_config = {
    .general = TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_2, GPIO_NUM_4, CAN_MODE_NORMAL),
    .filter = TWAI_FILTER_CONFIG_ACCEPT_ALL(),
    .timing = TWAI_TIMING_CONFIG_25KBITS(),
    .initialized = false
};

STATIC esp32_can_obj_t esp32_can_obj = {
    {&esp32_can_type},
    .config = &can_config
};

// INTERNAL FUNCTION Return status information
STATIC twai_status_info_t _esp32_hw_can_get_status() {
    twai_status_info_t status;
    check_esp_err(twai_get_status_info(&status));
    return status;
}

// INTERNAL FUNCTION Reset can filter to defaults
void esp32_reset_can_filter(const esp32_can_obj_t *self) {
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    self->config->filter.single_filter = f_config.single_filter;
    self->config->filter.acceptance_code = f_config.acceptance_code;
    self->config->filter.acceptance_mask = f_config.acceptance_mask;
}

STATIC void esp32_hw_can_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);

    if (self->config->initialized) {
        qstr mode = MP_QSTR_LISTEN;
        switch (self->config->general.mode) {
            case CAN_MODE_LOOPBACK:
                mode = MP_QSTR_LOOPBACK;
                break;
            case CAN_MODE_SILENT:
                mode = MP_QSTR_SILENT;
                break;
            case CAN_MODE_NORMAL:
                mode = MP_QSTR_NORMAL;
                break;
        }
        mp_printf(print, "CAN(tx=%u, rx=%u, baudrate=%ukb, mode=%q, loopback=%u)",
            self->config->general.tx_io,
            self->config->general.rx_io,
            self->config->baudrate,
            mode,
            self->loopback
            );
    } else {
        mp_printf(print, "Device is not initialized");
    }
}

// INTERNAL FUNCTION FreeRTOS IRQ task
STATIC void esp32_hw_can_irq_task(void *self_in) {
    esp32_can_obj_t *self = (esp32_can_obj_t *)self_in;
    uint32_t alerts;

    twai_reconfigure_alerts(
        TWAI_ALERT_RX_DATA | TWAI_ALERT_RX_QUEUE_FULL | TWAI_ALERT_BUS_OFF | TWAI_ALERT_ERR_PASS |
        TWAI_ALERT_ABOVE_ERR_WARN | TWAI_ALERT_TX_FAILED | TWAI_ALERT_TX_SUCCESS | TWAI_ALERT_BUS_RECOVERED,
        NULL
        );

    while (1) {
        check_esp_err(twai_read_alerts(&alerts, portMAX_DELAY));

        if (alerts & TWAI_ALERT_BUS_OFF) {
            ++self->num_bus_off;
        }
        if (alerts & TWAI_ALERT_ERR_PASS) {
            ++self->num_error_passive;
        }
        if (alerts & TWAI_ALERT_ABOVE_ERR_WARN) {
            ++self->num_error_warning;
        }

        if (alerts & (TWAI_ALERT_TX_FAILED | TWAI_ALERT_TX_SUCCESS)) {
            self->last_tx_success = (alerts & TWAI_ALERT_TX_SUCCESS) > 0;
        }

        if (alerts & (TWAI_ALERT_BUS_RECOVERED)) {
            self->bus_recovery_success = true;
        }

        if (self->rxcallback != mp_const_none) {
            if (alerts & TWAI_ALERT_RX_DATA) {
                uint32_t msgs_to_rx = _esp32_hw_can_get_status().msgs_to_rx;

                if (msgs_to_rx == 1) {
                    // first message in queue
                    mp_sched_schedule(self->rxcallback, MP_OBJ_NEW_SMALL_INT(0));
                } else if (msgs_to_rx >= self->config->general.rx_queue_len) {
                    // queue is full
                    mp_sched_schedule(self->rxcallback, MP_OBJ_NEW_SMALL_INT(1));
                }
            }
            if (alerts & TWAI_ALERT_RX_QUEUE_FULL) {
                // queue overflow
                mp_sched_schedule(self->rxcallback, MP_OBJ_NEW_SMALL_INT(2));
            }
        }
    }
}

// init(mode, tx=5, rx=4, baudrate=500000, prescaler=8, sjw=3, bs1=15, bs2=4, auto_restart=False, tx_queue=1, rx_queue=1)
STATIC mp_obj_t esp32_hw_can_init_helper(esp32_can_obj_t *self, size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_mode, ARG_prescaler, ARG_sjw, ARG_bs1, ARG_bs2, ARG_auto_restart, ARG_baudrate,
           ARG_tx_io, ARG_rx_io, ARG_tx_queue, ARG_rx_queue};
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_mode,         MP_ARG_REQUIRED | MP_ARG_INT,   {.u_int = CAN_MODE_NORMAL} },
        { MP_QSTR_prescaler,    MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = CAN_DEFAULT_PRESCALER} },
        { MP_QSTR_sjw,          MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = CAN_DEFAULT_SJW} },
        { MP_QSTR_bs1,          MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = CAN_DEFAULT_BS1} },
        { MP_QSTR_bs2,          MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = CAN_DEFAULT_BS2} },
        { MP_QSTR_auto_restart, MP_ARG_BOOL,                    {.u_bool = false} },
        { MP_QSTR_baudrate,     MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = 500000} },
        { MP_QSTR_tx,           MP_ARG_INT,                     {.u_int = 4} },
        { MP_QSTR_rx,           MP_ARG_INT,                     {.u_int = 5} },
        { MP_QSTR_tx_queue,     MP_ARG_INT,                     {.u_int = 1} },
        { MP_QSTR_rx_queue,     MP_ARG_INT,                     {.u_int = 1} },
    };

    // parse args
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    // Configure device
    const int mode = args[ARG_mode].u_int;
    self->loopback = false;
    self->config->baudrate = args[ARG_baudrate].u_int;
    if (mode == CAN_MODE_SILENT_LOOPBACK) {
        self->config->general.mode = TWAI_MODE_NO_ACK;
        self->loopback = true;
    } else {
        self->config->general.mode = mode & 0x0F;
    }
    self->config->general.tx_io = args[ARG_tx_io].u_int;
    self->config->general.rx_io = args[ARG_rx_io].u_int;
    self->config->general.clkout_io = TWAI_IO_UNUSED;
    self->config->general.bus_off_io = TWAI_IO_UNUSED;
    self->config->general.tx_queue_len = args[ARG_tx_queue].u_int;
    self->config->general.rx_queue_len = args[ARG_rx_queue].u_int;
    self->config->general.alerts_enabled = TWAI_ALERT_NONE;
    self->config->general.clkout_divider = 0;
    if (args[ARG_auto_restart].u_bool) {
        mp_raise_NotImplementedError("Auto-restart not supported");
    }
    esp32_reset_can_filter(self);

    // clear errors
    self->num_error_warning = 0;
    self->num_error_passive = 0;
    self->num_bus_off = 0;

    // Calculate CAN nominal bit timing from baudrate if provided
    twai_timing_config_t *timing;
    switch ((int)args[ARG_baudrate].u_int) {
        case 0:
            timing = &((twai_timing_config_t) {
            .brp = args[ARG_prescaler].u_int,
            .sjw = args[ARG_sjw].u_int,
            .tseg_1 = args[ARG_bs1].u_int,
            .tseg_2 = args[ARG_bs2].u_int,
            .triple_sampling = false
        });
            break;
        #ifdef TWAI_TIMING_CONFIG_1KBITS
        case 1000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_1KBITS());
            break;
        #endif
        #ifdef TWAI_TIMING_CONFIG_5KBITS
        case 5000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_5KBITS());
            break;
        #endif
        #ifdef TWAI_TIMING_CONFIG_10KBITS
        case 10000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_10KBITS());
            break;
        #endif
        #ifdef TWAI_TIMING_CONFIG_12_5KBITS
        case 12500:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_12_5KBITS());
            break;
        #endif
        #ifdef TWAI_TIMING_CONFIG_16KBITS
        case 16000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_16KBITS());
            break;
        #endif
        #ifdef TWAI_TIMING_CONFIG_20KBITS
        case 20000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_20KBITS());
            break;
        #endif
        case 25000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_25KBITS());
            break;
        case 50000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_50KBITS());
            break;
        case 100000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_100KBITS());
            break;
        case 125000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_125KBITS());
            break;
        case 250000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_250KBITS());
            break;
        case 500000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_500KBITS());
            break;
        case 800000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_800KBITS());
            break;
        case 1000000:
            timing = &((twai_timing_config_t)TWAI_TIMING_CONFIG_1MBITS());
            break;
        default:
            mp_raise_ValueError("Unable to set baudrate");
            self->config->baudrate = 0;
            return mp_const_none;
    }
    self->config->timing = *timing;

    check_esp_err(twai_driver_install(&self->config->general, &self->config->timing, &self->config->filter));
    check_esp_err(twai_start());
    if (xTaskCreatePinnedToCore(esp32_hw_can_irq_task, "can_irq_task", CAN_TASK_STACK_SIZE, self, CAN_TASK_PRIORITY, (TaskHandle_t *)&self->irq_handler, MP_TASK_COREID) != pdPASS) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("failed to create can irq task handler"));
    }
    self->config->initialized = true;

    return mp_const_none;
}

// CAN(bus, ...) No argument to get the object
STATIC mp_obj_t esp32_hw_can_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    // check arguments
    mp_arg_check_num(n_args, n_kw, 1, MP_OBJ_FUN_ARGS_MAX, true);
    if (mp_obj_is_int(args[0]) != true) {
        mp_raise_TypeError("bus must be a number");
    }

    // work out port
    mp_uint_t can_idx = mp_obj_get_int(args[0]);
    if (can_idx != 0) {
        mp_raise_msg_varg(&mp_type_ValueError, "CAN(%d) doesn't exist", can_idx);
    }

    esp32_can_obj_t *self = &esp32_can_obj;
    if (!self->config->initialized || n_args > 1 || n_kw > 0) {
        if (self->config->initialized) {
            // The caller is requesting a reconfiguration of the hardware
            // this can only be done if the hardware is in init mode
            can_deinit(self);
        }
        self->rxcallback = mp_const_none;
        self->irq_handler = NULL;

        if (n_args > 1 || n_kw > 0) {
            // start the peripheral
            mp_map_t kw_args;
            mp_map_init_fixed_table(&kw_args, n_kw, args + n_args);
            esp32_hw_can_init_helper(self, n_args - 1, args + 1, &kw_args);
        }
    }
    return MP_OBJ_FROM_PTR(self);
}

// init(tx, rx, baudrate, mode=CAN_MODE_NORMAL, tx_queue=2, rx_queue=5)
STATIC mp_obj_t esp32_hw_can_init(size_t n_args, const mp_obj_t *args, mp_map_t *kw_args) {
    return esp32_hw_can_init_helper(MP_OBJ_TO_PTR(args[0]), n_args - 1, args + 1, kw_args);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(esp32_hw_can_init_obj, 1, esp32_hw_can_init);

// deinit()
STATIC mp_obj_t esp32_hw_can_deinit(const mp_obj_t self_in) {
    const esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);
    can_deinit(self);
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_deinit_obj, esp32_hw_can_deinit);

// Force a software restart of the controller, to allow transmission after a bus error
STATIC mp_obj_t esp32_hw_can_restart(mp_obj_t self_in) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);
    twai_status_info_t status = _esp32_hw_can_get_status();
    if (!self->config->initialized || status.state != TWAI_STATE_BUS_OFF) {
        mp_raise_ValueError(NULL);
    }

    self->bus_recovery_success = -1;
    check_esp_err(twai_initiate_recovery());

    while (self->bus_recovery_success < 0) {
        MICROPY_EVENT_POLL_HOOK
    }

    if (self->bus_recovery_success) {
        check_esp_err(twai_start());
    } else {
        mp_raise_OSError(MP_EIO);
    }
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_restart_obj, esp32_hw_can_restart);

// Get the state of the controller
STATIC mp_obj_t esp32_hw_can_state(mp_obj_t self_in) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);
    mp_int_t state = TWAI_STATE_STOPPED;
    if (self->config->initialized) {
        state = _esp32_hw_can_get_status().state;
    }
    return mp_obj_new_int(state);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_state_obj, esp32_hw_can_state);

// info() -- Get info about error states and TX/RX buffers
STATIC mp_obj_t esp32_hw_can_info(size_t n_args, const mp_obj_t *args) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(args[0]);
    mp_obj_list_t *list;
    if (n_args == 1) {
        list = MP_OBJ_TO_PTR(mp_obj_new_list(7, NULL));
    } else {
        if (!mp_obj_is_type(args[1], &mp_type_list)) {
            mp_raise_TypeError(NULL);
        }
        list = MP_OBJ_TO_PTR(args[1]);
        if (list->len < 7) {
            mp_raise_ValueError(NULL);
        }
    }
    twai_status_info_t status = _esp32_hw_can_get_status();
    list->items[0] = MP_OBJ_NEW_SMALL_INT(status.tx_error_counter);
    list->items[1] = MP_OBJ_NEW_SMALL_INT(status.rx_error_counter);
    list->items[2] = MP_OBJ_NEW_SMALL_INT(self->num_error_warning);
    list->items[3] = MP_OBJ_NEW_SMALL_INT(self->num_error_passive);
    list->items[4] = MP_OBJ_NEW_SMALL_INT(self->num_bus_off);
    list->items[5] = MP_OBJ_NEW_SMALL_INT(status.msgs_to_tx);
    list->items[6] = MP_OBJ_NEW_SMALL_INT(status.msgs_to_rx);
    return MP_OBJ_FROM_PTR(list);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(esp32_hw_can_info_obj, 1, 2, esp32_hw_can_info);

// any() - return `True` if any message waiting, else `False`
STATIC mp_obj_t esp32_hw_can_any(mp_obj_t self_in) {
    twai_status_info_t status = _esp32_hw_can_get_status();
    return mp_obj_new_bool((status.msgs_to_rx) > 0);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_any_obj, esp32_hw_can_any);

// send([data], id, *, timeout=0, rtr=false, extframe=false)
STATIC mp_obj_t esp32_hw_can_send(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_data, ARG_id, ARG_timeout, ARG_rtr, ARG_extframe };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_data,     MP_ARG_REQUIRED | MP_ARG_OBJ,   {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_id,       MP_ARG_REQUIRED | MP_ARG_INT,   {.u_int = 0} },
        { MP_QSTR_timeout,  MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = 0} },
        { MP_QSTR_rtr,      MP_ARG_KW_ONLY | MP_ARG_BOOL,   {.u_bool = false} },
        { MP_QSTR_extframe, MP_ARG_BOOL,                    {.u_bool = false} },
    };

    // parse args
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(pos_args[0]);
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args - 1, pos_args + 1, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    // populate message
    twai_message_t tx_msg;

    size_t length;
    mp_obj_t *items;
    mp_obj_get_array(args[ARG_data].u_obj, &length, &items);
    if (length > CAN_MAX_DATA_FRAME) {
        mp_raise_ValueError("CAN data field too long");
    }
    tx_msg.data_length_code = length;
    tx_msg.flags = (args[ARG_rtr].u_bool ? TWAI_MSG_FLAG_RTR : TWAI_MSG_FLAG_NONE);

    if (args[ARG_extframe].u_bool) {
        tx_msg.identifier = args[ARG_id].u_int & 0x1FFFFFFF;
        tx_msg.flags += TWAI_MSG_FLAG_EXTD;
    } else {
        tx_msg.identifier = args[ARG_id].u_int & 0x7FF;
    }
    if (self->loopback) {
        tx_msg.flags += TWAI_MSG_FLAG_SELF;
    }

    for (uint8_t i = 0; i < length; i++) {
        tx_msg.data[i] = mp_obj_get_int(items[i]);
    }

    if (_esp32_hw_can_get_status().state == TWAI_STATE_RUNNING) {
        uint32_t timeout_ms = args[ARG_timeout].u_int;

        if (timeout_ms != 0) {
            self->last_tx_success = -1;
            uint32_t start = mp_hal_ticks_us();
            check_esp_err(twai_transmit(&tx_msg, pdMS_TO_TICKS(timeout_ms)));
            while (self->last_tx_success < 0) {
                if (timeout_ms != portMAX_DELAY) {
                    if (mp_hal_ticks_us() - start >= timeout_ms) {
                        mp_raise_OSError(MP_ETIMEDOUT);
                    }
                }
                MICROPY_EVENT_POLL_HOOK
            }

            if (!self->last_tx_success) {
                mp_raise_OSError(MP_EIO);
            }
        } else {
            check_esp_err(twai_transmit(&tx_msg, portMAX_DELAY));
        }

        return mp_const_none;
    } else {
        mp_raise_msg(&mp_type_RuntimeError, "Device is not ready");
    }
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(esp32_hw_can_send_obj, 3, esp32_hw_can_send);

// recv(list=None, *, timeout=5000)
STATIC mp_obj_t esp32_hw_can_recv(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_list, ARG_timeout };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_list,     MP_ARG_OBJ,                     {.u_rom_obj = MP_ROM_NONE} },
        { MP_QSTR_timeout,  MP_ARG_KW_ONLY | MP_ARG_INT,    {.u_int = 5000} },
    };

    // parse args
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args - 1, pos_args + 1, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    // receive the data
    twai_message_t rx_msg;
    check_esp_err(twai_receive(&rx_msg, pdMS_TO_TICKS(args[ARG_timeout].u_int)));
    uint32_t rx_dlc = rx_msg.data_length_code;

    // Create the tuple, or get the list, that will hold the return values
    // Also populate the fifth element, either a new bytes or reuse existing memoryview
    mp_obj_t ret_obj = args[ARG_list].u_obj;
    mp_obj_t *items;
    if (ret_obj == mp_const_none) {
        ret_obj = mp_obj_new_tuple(4, NULL);
        items = ((mp_obj_tuple_t *)MP_OBJ_TO_PTR(ret_obj))->items;
        items[3] = mp_obj_new_bytes(rx_msg.data, rx_dlc);
    } else {
        // User should provide a list of length at least 5 to hold the values
        if (!mp_obj_is_type(ret_obj, &mp_type_list)) {
            mp_raise_TypeError(NULL);
        }
        mp_obj_list_t *list = MP_OBJ_TO_PTR(ret_obj);
        if (list->len < 4) {
            mp_raise_ValueError(NULL);
        }
        items = list->items;
        // Fifth element must be a memoryview which we assume points to a
        // byte-like array which is large enough, and then we resize it inplace
        if (!mp_obj_is_type(items[3], &mp_type_memoryview)) {
            mp_raise_TypeError(NULL);
        }
        mp_obj_array_t *mv = MP_OBJ_TO_PTR(items[3]);
        if (!(mv->typecode == (MP_OBJ_ARRAY_TYPECODE_FLAG_RW | BYTEARRAY_TYPECODE)
              || (mv->typecode | 0x20) == (MP_OBJ_ARRAY_TYPECODE_FLAG_RW | 'b'))) {
            mp_raise_ValueError(NULL);
        }
        mv->len = rx_dlc;
        memcpy(mv->items, rx_msg.data, rx_dlc);
    }

    items[0] = MP_OBJ_NEW_SMALL_INT(rx_msg.identifier);
    items[1] = rx_msg.extd ? mp_const_true : mp_const_false;
    items[2] = rx_msg.rtr ? mp_const_true : mp_const_false;

    // Return the result
    return ret_obj;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(esp32_hw_can_recv_obj, 0, esp32_hw_can_recv);

// Clear filters setting
STATIC mp_obj_t esp32_hw_can_clearfilter(mp_obj_t self_in) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);

    // Defaults from TWAI_FILTER_CONFIG_ACCEPT_ALL
    self->config->filter.single_filter = true;
    self->config->filter.acceptance_code = 0;
    self->config->filter.acceptance_mask = 0xFFFFFFFF;

    // Apply filter
    check_esp_err(twai_stop());
    check_esp_err(twai_driver_uninstall());
    check_esp_err(twai_driver_install(
        &self->config->general,
        &self->config->timing,
        &self->config->filter));
    check_esp_err(twai_start());
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_clearfilter_obj, esp32_hw_can_clearfilter);

// bank: 0 only
// mode: FILTER_RAW_SINGLE, FILTER_RAW_DUAL or FILTER_ADDR_SINGLE or FILTER_ADDR_DUAL
// params: [id, mask]
// rtr: ignored if FILTER_RAW
// Set CAN HW filter
STATIC mp_obj_t esp32_hw_can_setfilter(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_bank, ARG_mode, ARG_params, ARG_rtr, ARG_extframe };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_bank,     MP_ARG_REQUIRED | MP_ARG_INT,   {.u_int = 0} },
        { MP_QSTR_mode,     MP_ARG_REQUIRED | MP_ARG_INT,   {.u_int = 0} },
        { MP_QSTR_params,   MP_ARG_REQUIRED | MP_ARG_OBJ,   {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_rtr,      MP_ARG_KW_ONLY | MP_ARG_OBJ,    {.u_rom_obj = MP_ROM_NONE} },
        { MP_QSTR_extframe, MP_ARG_BOOL,                    {.u_bool = false} },
    };

    // parse args
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(pos_args[0]);
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args - 1, pos_args + 1, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);
    const int can_idx = args[ARG_bank].u_int;

    if (can_idx != 0) {
        mp_raise_msg_varg(&mp_type_ValueError, "Bank (%d) doesn't exist", can_idx);
    }

    size_t len;
    mp_obj_t *params;
    mp_obj_get_array(args[ARG_params].u_obj, &len, &params);
    const int mode = args[ARG_mode].u_int;

    if (mode == FILTER_RAW_SINGLE || mode == FILTER_RAW_DUAL) {
        if (len != 2) {
            mp_raise_ValueError("params must be a 2-values list");
        }
        self->config->filter.single_filter = (mode == FILTER_RAW_SINGLE);
        self->config->filter.acceptance_code = mp_obj_get_int_truncated(params[0]);
        self->config->filter.acceptance_mask = mp_obj_get_int_truncated(params[1]);
    } else {
        uint32_t code = 0x0;
        uint32_t mask = 0xffffffff;
        const bool has_rtr = args[ARG_rtr].u_obj != mp_const_none;
        const bool rtr = args[ARG_rtr].u_obj == mp_const_true;
        const bool extframe = args[ARG_extframe].u_bool;

        if (extframe) {
            // bitmap: [29 bits id, rtr, 2 bits reserved]
            if (len != 1) {
                mp_raise_ValueError("params must be a 1-values list");
            }
            code |= mp_obj_get_int_truncated(params[0]) << 3;  // move to first 29 bits
            mask &= ~(0x1fffffff << 3);  // set first 29 bits to zeros
            if (has_rtr) {
                mask ^= 1 << 2;
                const int rtr_bit = 1 << 2;
                if (rtr) {
                    code |= rtr_bit;
                } else {
                    code &= ~rtr_bit;
                }
            }
        } else {
            // bitmap: [11 bits id, rtr, 4 bits reserved, 8 bits data_byte_1, 8 bits data_byte_2]
            if (len == 0) {
                mp_raise_ValueError("params must not be empty");
            }
            code |= mp_obj_get_int_truncated(params[0]) << 21;  // move to first 11 bits
            mask &= ~(0x7ff << 21);  // set first 11 bits to zeros
            if (has_rtr) {
                mask ^= 1 << 20;
                const int rtr_bit = 1 << 20;
                if (rtr) {
                    code |= rtr_bit;
                } else {
                    code &= ~rtr_bit;
                }
            }
            // Set data filter bits
            if (len > 1) {
                // set data_byte_1
                code |= mp_obj_get_int_truncated(params[1]) << 8;
                mask &= ~(0xff << 8);
            }
            if (len > 2) {
                // set data_byte_2
                code |= mp_obj_get_int_truncated(params[2]) << 0;
                mask &= ~(0xff << 0);
            }
        }

        // Always use single filter mode for addr filter
        self->config->filter.single_filter = true;
        self->config->filter.acceptance_code = code;
        self->config->filter.acceptance_mask = mask;
    }

    // Apply filter
    check_esp_err(twai_stop());
    check_esp_err(twai_driver_uninstall());
    check_esp_err(twai_driver_install(
        &self->config->general,
        &self->config->timing,
        &self->config->filter
        ));
    check_esp_err(twai_start());

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(esp32_hw_can_setfilter_obj, 1, esp32_hw_can_setfilter);

// rxcallback(callable)
STATIC mp_obj_t esp32_hw_can_rxcallback(mp_obj_t self_in, mp_obj_t callback_in) {
    esp32_can_obj_t *self = MP_OBJ_TO_PTR(self_in);

    if (callback_in == mp_const_none) {
        // disable callback
        self->rxcallback = mp_const_none;
    } else if (mp_obj_is_callable(callback_in)) {
        // set up interrupt
        self->rxcallback = callback_in;
    }

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(esp32_hw_can_rxcallback_obj, esp32_hw_can_rxcallback);

// Clear TX Queue
STATIC mp_obj_t esp32_hw_can_clear_tx_queue(mp_obj_t self_in) {
    return mp_obj_new_bool(twai_clear_transmit_queue() == ESP_OK);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_clear_tx_queue_obj, esp32_hw_can_clear_tx_queue);

// Clear RX Queue
STATIC mp_obj_t esp32_hw_can_clear_rx_queue(mp_obj_t self_in) {
    return mp_obj_new_bool(twai_clear_receive_queue() == ESP_OK);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(esp32_hw_can_clear_rx_queue_obj, esp32_hw_can_clear_rx_queue);

STATIC const mp_rom_map_elem_t esp32_can_locals_dict_table[] = {
    // CAN_ATTRIBUTES
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_CAN) },
    // Micropython Generic API
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&esp32_hw_can_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_deinit), MP_ROM_PTR(&esp32_hw_can_deinit_obj) },
    { MP_ROM_QSTR(MP_QSTR_restart), MP_ROM_PTR(&esp32_hw_can_restart_obj) },
    { MP_ROM_QSTR(MP_QSTR_state), MP_ROM_PTR(&esp32_hw_can_state_obj) },
    { MP_ROM_QSTR(MP_QSTR_info), MP_ROM_PTR(&esp32_hw_can_info_obj) },
    { MP_ROM_QSTR(MP_QSTR_any), MP_ROM_PTR(&esp32_hw_can_any_obj) },
    { MP_ROM_QSTR(MP_QSTR_send), MP_ROM_PTR(&esp32_hw_can_send_obj) },
    { MP_ROM_QSTR(MP_QSTR_recv), MP_ROM_PTR(&esp32_hw_can_recv_obj) },
    { MP_ROM_QSTR(MP_QSTR_setfilter), MP_ROM_PTR(&esp32_hw_can_setfilter_obj) },
    { MP_ROM_QSTR(MP_QSTR_clearfilter), MP_ROM_PTR(&esp32_hw_can_clearfilter_obj) },
    { MP_ROM_QSTR(MP_QSTR_rxcallback), MP_ROM_PTR(&esp32_hw_can_rxcallback_obj) },
    // ESP32 Specific API
    { MP_OBJ_NEW_QSTR(MP_QSTR_clear_tx_queue), MP_ROM_PTR(&esp32_hw_can_clear_tx_queue_obj) },
    { MP_OBJ_NEW_QSTR(MP_QSTR_clear_rx_queue), MP_ROM_PTR(&esp32_hw_can_clear_rx_queue_obj) },
    // CAN_MODE
    { MP_ROM_QSTR(MP_QSTR_NORMAL), MP_ROM_INT(CAN_MODE_NORMAL) },
    { MP_ROM_QSTR(MP_QSTR_LOOPBACK), MP_ROM_INT(CAN_MODE_LOOPBACK) },
    { MP_ROM_QSTR(MP_QSTR_SILENT), MP_ROM_INT(CAN_MODE_SILENT) },
    { MP_ROM_QSTR(MP_QSTR_SILENT_LOOPBACK), MP_ROM_INT(CAN_MODE_SILENT_LOOPBACK) },
    // CAN_STATE
    { MP_ROM_QSTR(MP_QSTR_STOPPED), MP_ROM_INT(TWAI_STATE_STOPPED) },
    { MP_ROM_QSTR(MP_QSTR_ERROR_ACTIVE), MP_ROM_INT(TWAI_STATE_RUNNING) },
    { MP_ROM_QSTR(MP_QSTR_BUS_OFF), MP_ROM_INT(TWAI_STATE_BUS_OFF) },
    { MP_ROM_QSTR(MP_QSTR_RECOVERING), MP_ROM_INT(TWAI_STATE_RECOVERING) },
    // CAN_FILTER_MODE
    { MP_ROM_QSTR(MP_QSTR_FILTER_RAW_SINGLE), MP_ROM_INT(FILTER_RAW_SINGLE) },
    { MP_ROM_QSTR(MP_QSTR_FILTER_RAW_DUAL), MP_ROM_INT(FILTER_RAW_DUAL) },
    { MP_ROM_QSTR(MP_QSTR_FILTER_ADDRESS), MP_ROM_INT(FILTER_ADDRESS) },
};
STATIC MP_DEFINE_CONST_DICT(esp32_can_locals_dict, esp32_can_locals_dict_table);

// Python object definition
MP_DEFINE_CONST_OBJ_TYPE(
    esp32_can_type,
    MP_QSTR_CAN,
    MP_TYPE_FLAG_NONE,
    make_new, esp32_hw_can_make_new,
    print, esp32_hw_can_print,
    locals_dict, (mp_obj_dict_t *)&esp32_can_locals_dict
    );

// Define all attributes of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t esp32can_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_esp32can) },
    { MP_ROM_QSTR(MP_QSTR_CAN),    MP_ROM_PTR(&esp32_can_type) },
};
STATIC MP_DEFINE_CONST_DICT(esp32can_module_globals, esp32can_module_globals_table);

// Define module object.
const mp_obj_module_t esp32can_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&esp32can_module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_esp32can, esp32can_module);


#endif // MICROPY_HW_ENABLE_CAN