# board to build (in ./boards folder)
BOARD=ESP32_S3_N16R8

TAG := $(shell date +"%Y.%m.%d")

PORT_DIR=micropython/ports/esp32
BUILD_DIR=${PORT_DIR}/build-${BOARD}
FIRMWARE_DIR=firmware/${BOARD}/${TAG}
LATEST_FIRMWARE_DIR=firmware/${BOARD}/latest
GITHUB_REPOSITORY=iot49/leaf
IDF_VERSION=v5.2.2



.PHONY: build dependencies flash

build: dependencies clean
	cd ../..; \
	docker run --rm \
		-v .:/project -w /project/trees/vm/micropython \
		espressif/idf:${IDF_VERSION} \
		bash -c " \
  			make -C mpy-cross; \
  			make -C ports/esp32 BOARD=${BOARD} clean; \
			make -C ports/esp32 V=1 \
				BOARD=${BOARD} \
 				USER_C_MODULES=../../../../src/modules/micropython.cmake \
				FROZEN_MANIFEST=../../../../../../src/freeze/manifest.py"
				
	@echo Copy compiled firmware to ${FIRMWARE_DIR}
	mkdir -p ${FIRMWARE_DIR}
	mkdir -p ${LATEST_FIRMWARE_DIR}
	cp ${BUILD_DIR}/{firmware.bin,micropython.bin} ${FIRMWARE_DIR}
	cp ${BUILD_DIR}/{firmware.bin,micropython.bin} ${LATEST_FIRMWARE_DIR}

	@echo Cleaning up
	rm -rf ${BUILD_DIR}
	rm -rf ${PORT_DIR}/boards/${BOARD}
	rm -rf ${PORT_DIR}/partition-S3-N16-custom.csv


dependencies:
	git submodule update --init micropython
	cd micropython; git submodule update --init lib/berkeley-db-1.xx lib/micropython-lib
	make -C micropython/ports/esp32 submodules

	# is there a way for micropython to look for boards in a different directory?
	# until I find out - just copy the files!
	mkdir -p micropython/ports/esp32/boards
	cp -a boards/${BOARD} micropython/ports/esp32/boards
	cp micropython/ports/esp32/boards/${BOARD}/partition* micropython/ports/esp32

flash:
	@ls /dev/*usb*
	# esptool.py erase_flash
	esptool.py --chip esp32s3 write_flash -z 0 firmware/${BOARD}/latest/firmware.bin

flash-download:
	@ls /dev/*usb*
	esptool.py erase_flash
	esptool.py --chip esp32s3 write_flash -z 0 ~/Downloads/UM_PROS3*.bin

clean:
	@echo "Removing python cache files..."
	find ../.. -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete


