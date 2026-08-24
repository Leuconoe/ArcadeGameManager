from __future__ import annotations

import ctypes
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageTk


def load_thumbnail(path: Path, max_size: tuple[int, int] = (320, 230)) -> ImageTk.PhotoImage:
    with Image.open(path) as source:
        image = source.convert("RGBA")

    return ImageTk.PhotoImage(artwork_with_blurred_background(image, max_size))


def artwork_with_blurred_background(image: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    """Place sharp artwork over a color-rich, heavily blurred enlargement of itself."""
    foreground = image.convert("RGBA")
    dominant = dominant_opaque_color(foreground)
    flattened = Image.new("RGBA", foreground.size, (*dominant, 255))
    flattened.alpha_composite(foreground)
    background = ImageOps.fit(flattened.convert("RGB"), canvas_size, Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=max(14, min(canvas_size) // 7)))
    background = ImageEnhance.Color(background).enhance(1.25)
    background = ImageEnhance.Contrast(background).enhance(0.88)

    sharp = foreground.copy()
    has_transparency = foreground.getchannel("A").getextrema()[0] < 255
    padding = max(10, min(canvas_size) // 12) if has_transparency else 0
    sharp.thumbnail(
        (max(1, canvas_size[0] - padding * 2), max(1, canvas_size[1] - padding * 2)),
        Image.Resampling.LANCZOS,
    )
    x = (canvas_size[0] - sharp.width) // 2
    y = (canvas_size[1] - sharp.height) // 2
    background.paste(sharp, (x, y), sharp)
    return background


def dominant_opaque_color(image: Image.Image) -> tuple[int, int, int]:
    """Return the most-used visible color group, weighted by pixel alpha."""
    sample = image.convert("RGBA")
    sample.thumbnail((192, 192), Image.Resampling.BOX)

    # Nearby colors caused by scaling/anti-aliasing belong to the same 16-wide bin.
    bins: dict[tuple[int, int, int], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for red, green, blue, alpha in sample.getdata():
        if alpha < 16:
            continue
        key = (red // 16, green // 16, blue // 16)
        values = bins[key]
        values[0] += alpha
        values[1] += red * alpha
        values[2] += green * alpha
        values[3] += blue * alpha

    if not bins:
        return (32, 32, 32)

    weight, red_sum, green_sum, blue_sum = max(bins.values(), key=lambda item: item[0])
    return (red_sum // weight, green_sum // weight, blue_sum // weight)


def load_executable_icon(
    path: Path,
    max_size: tuple[int, int] = (96, 96),
    canvas_size: tuple[int, int] | None = None,
) -> ImageTk.PhotoImage:
    """Extract the primary Windows icon from an EXE without extra dependencies."""
    if sys.platform != "win32":
        raise OSError("실행 파일 아이콘 추출은 Windows에서만 지원합니다.")
    if not path.is_file():
        raise FileNotFoundError(f"실행 파일을 찾을 수 없습니다: {path}")

    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    shell32.ExtractIconExW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.UINT,
    ]
    shell32.ExtractIconExW.restype = wintypes.UINT
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.DrawIconEx.argtypes = [
        wintypes.HDC,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.HBRUSH,
        wintypes.UINT,
    ]
    user32.DrawIconEx.restype = wintypes.BOOL
    user32.DestroyIcon.argtypes = [wintypes.HANDLE]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFO),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi32.SelectObject.restype = wintypes.HANDLE
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    large_icon = wintypes.HANDLE()
    small_icon = wintypes.HANDLE()
    extracted = shell32.ExtractIconExW(str(path), 0, ctypes.byref(large_icon), ctypes.byref(small_icon), 1)
    icon = large_icon.value or small_icon.value
    if extracted == 0 or not icon:
        raise ValueError(f"실행 파일에서 아이콘을 찾지 못했습니다: {path.name}")

    width = height = 256
    screen_dc = user32.GetDC(None)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bits = ctypes.c_void_p()
    bitmap_info = BITMAPINFO()
    bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bitmap_info.bmiHeader.biWidth = width
    bitmap_info.bmiHeader.biHeight = -height
    bitmap_info.bmiHeader.biPlanes = 1
    bitmap_info.bmiHeader.biBitCount = 32
    bitmap_info.bmiHeader.biCompression = 0
    bitmap = gdi32.CreateDIBSection(memory_dc, ctypes.byref(bitmap_info), 0, ctypes.byref(bits), None, 0)
    if not bitmap:
        user32.ReleaseDC(None, screen_dc)
        gdi32.DeleteDC(memory_dc)
        user32.DestroyIcon(large_icon)
        if small_icon.value:
            user32.DestroyIcon(small_icon)
        raise OSError("실행 파일 아이콘용 비트맵을 만들지 못했습니다.")

    previous = gdi32.SelectObject(memory_dc, bitmap)
    try:
        blue, green, red = COLORS_FALLBACK[2], COLORS_FALLBACK[1], COLORS_FALLBACK[0]
        background_bytes = bytes((blue, green, red, 255)) * (width * height)
        ctypes.memmove(bits, background_bytes, len(background_bytes))
        if not user32.DrawIconEx(memory_dc, 0, 0, icon, width, height, 0, None, 0x0003):
            raise OSError(f"실행 파일 아이콘을 그리지 못했습니다: {path.name}")
        raw = ctypes.string_at(bits, width * height * 4)
        rendered = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
        flat_background = Image.new("RGB", rendered.size, COLORS_FALLBACK)
        difference = ImageChops.difference(rendered, flat_background).convert("L")
        alpha = difference.point(lambda value: min(255, value * 6))
        image = rendered.convert("RGBA")
        image.putalpha(alpha)
        bounds = alpha.getbbox()
        if bounds:
            image = image.crop(bounds)
        target_size = canvas_size or max_size
        return ImageTk.PhotoImage(artwork_with_blurred_background(image, target_size))
    finally:
        gdi32.SelectObject(memory_dc, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(None, screen_dc)
        if large_icon.value:
            user32.DestroyIcon(large_icon)
        if small_icon.value:
            user32.DestroyIcon(small_icon)


COLORS_FALLBACK = (240, 243, 248)
