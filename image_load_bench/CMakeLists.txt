cmake_minimum_required(VERSION 3.20)
project(image_load_bench CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Reuse the exact FreeImage build Falcor itself links against (packman-fetched), so the
# "FreeImage" result in this benchmark is a fair baseline for what Falcor actually pays.
set(FREEIMAGE_ROOT "C:/packman-repo/chk/falcor_dependencies/f80dd590-windows-x86_64")

# libvips 8.18.6, prebuilt MXE/MinGW package (deps/vips/, see fetch_deps.md). Its shipped
# .lib files are GNU-ar format and unreadable by MSVC's linker - vips_msvc.lib/glib_msvc.lib/
# gobject_msvc.lib were regenerated from the DLLs' export tables instead (dumpbin /exports ->
# a .def file -> `lib /def:`), which only works because libvips's public C API has plain,
# unmangled names (its C++ wrapper, libvips-cpp.dll, is NOT usable this way).
set(VIPS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/deps/vips/vips-dev-8.18")

# DevIL Windows SDK 1.8.0, prebuilt MSVC binaries from SourceForge (deps/devil/) - already
# MSVC-compatible, no relinking needed.
set(DEVIL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/deps/devil/DevIL Windows SDK")

# OpenImageIO - no prebuilt Windows dev package exists anywhere (official releases are
# source-only; the one community binary mirror found had DLLs but no headers/import libs),
# so this was built from source via a real vcpkg checkout (deps/vcpkg/) instead:
#   deps/vcpkg/bootstrap-vcpkg.bat
#   deps/vcpkg/vcpkg install openimageio:x64-windows --x-install-root=deps/vcpkg_installed
# vcpkg builds natively with MSVC, so unlike libvips's MinGW package, nothing needed
# relinking. Pointing CMAKE_PREFIX_PATH at the install tree (rather than using vcpkg's full
# toolchain file) lets find_package() below resolve OpenImageIO's own transitive
# dependencies (OpenEXR/Imath/etc., installed into the same tree) without it affecting how
# the other three libraries above are found by hand-specified path.
list(APPEND CMAKE_PREFIX_PATH "${CMAKE_CURRENT_SOURCE_DIR}/deps/vcpkg_installed/x64-windows")
find_package(OpenImageIO CONFIG REQUIRED)

add_executable(image_load_bench main.cpp rgbe_ref/rgbe.c)
target_include_directories(image_load_bench PRIVATE
    "${FREEIMAGE_ROOT}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${VIPS_ROOT}/include"
    "${VIPS_ROOT}/include/glib-2.0"
    "${VIPS_ROOT}/lib/glib-2.0/include"
    "${DEVIL_ROOT}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/deps/vcpkg_installed/x64-windows/include"
)
target_link_libraries(image_load_bench PRIVATE
    "${FREEIMAGE_ROOT}/lib/FreeImage.lib"
    "${VIPS_ROOT}/vips_msvc.lib"
    "${VIPS_ROOT}/glib_msvc.lib"
    "${VIPS_ROOT}/gobject_msvc.lib"
    "${DEVIL_ROOT}/lib/x64/Release/DevIL.lib"
    OpenImageIO::OpenImageIO
)

# Needed for the _mm256_i32gather_ps AVX2 intrinsic used by the CustomRGBE-AVX2 variant.
# MSVC applies /arch: per translation unit (no per-function target attributes like GCC/
# Clang), so this affects codegen for all of main.cpp, not just that one function - fine on
# any CPU from roughly the last decade (this machine's RTX 4050 implies one).
if (MSVC)
    target_compile_options(image_load_bench PRIVATE /arch:AVX2)
endif()

# OpenMP - used by the CustomRGBE-LUT-MT variant (two-pass parallel RLE decode).
find_package(OpenMP REQUIRED)
target_link_libraries(image_load_bench PRIVATE OpenMP::OpenMP_CXX)

# All dependencies' DLLs need to sit next to the exe to actually run - copying whole
# directories rather than hand-picking exact dependency sets (FreeImage's OpenEXR chain,
# libvips's ~60 transitive DLLs, DevIL's ILU/ILUT, OpenImageIO's OpenEXR/Imath/libtiff/etc.).
add_custom_command(TARGET image_load_bench POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${FREEIMAGE_ROOT}/bin" "$<TARGET_FILE_DIR:image_load_bench>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${VIPS_ROOT}/bin" "$<TARGET_FILE_DIR:image_load_bench>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${DEVIL_ROOT}/lib/x64/Release" "$<TARGET_FILE_DIR:image_load_bench>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_CURRENT_SOURCE_DIR}/deps/vcpkg_installed/x64-windows/bin" "$<TARGET_FILE_DIR:image_load_bench>"
)
