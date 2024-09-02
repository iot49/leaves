CEXAMPLE_MOD_DIR := $(USERMOD_DIR)

# Add all C files to SRC_USERMOD.
SRC_USERMOD += $(CEXAMPLE_MOD_DIR)/esp32_can.c

# Add module folder to include paths if needed
CFLAGS_USERMOD += -I$(CEXAMPLE_MOD_DIR)
