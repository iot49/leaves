# Create an INTERFACE library for C module.
add_library(usermod_esp32can INTERFACE)

# Add source files to the lib
target_sources(usermod_esp32can INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/esp32_can.c
)

# Add the current directory as an include directory.
target_include_directories(usermod_esp32can INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Link INTERFACE library to the usermod target.
target_link_libraries(usermod INTERFACE usermod_esp32can)
