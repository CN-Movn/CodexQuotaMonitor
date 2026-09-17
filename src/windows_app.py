"""Windows-only tray and hover quota card UI implemented with ctypes."""

from __future__ import annotations

import ctypes
import math
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

from scanner import (
    QuotaSnapshot,
    SessionScanner,
    format_reset,
    format_updated,
)


if os.name != "nt":  # pragma: no cover - this module targets Windows.
    raise RuntimeError("windows_app is only available on Windows")


APP_NAME = "Codex Quota Monitor"
TRAY_CLASS = "CodexQuotaMonitorTrayWindow"
HOVER_CLASS = "CodexQuotaMonitorHoverWindow"

WM_APP = 0x8000
WM_REFRESH_READY = WM_APP + 1
WM_TRAY_CALLBACK = WM_APP + 2

WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_CONTEXTMENU = 0x007B
WM_DESTROY = 0x0002
WM_ERASEBKGND = 0x0014
WM_MOUSEMOVE = 0x0200
WM_NCHITTEST = 0x0084
WM_PAINT = 0x000F
WM_RBUTTONUP = 0x0205
WM_TIMER = 0x0113

HTTRANSPARENT = -1
PM_REMOVE = 0x0001
TIMER_HOVER = 1

SW_HIDE = 0
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008

MF_SEPARATOR = 0x00000800
MF_STRING = 0x00000000
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

SPI_GETWORKAREA = 0x0030
LWA_ALPHA = 0x00000002
FW_SEMIBOLD = 600
DEFAULT_CHARSET = 1
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
CLEARTYPE_QUALITY = 5
DEFAULT_PITCH = 0
FF_DONTCARE = 0
DT_CENTER = 0x00000001
DT_LEFT = 0x00000000
DT_RIGHT = 0x00000002
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
DT_NOPREFIX = 0x00000800
TRANSPARENT = 1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
DIB_RGB_COLORS = 0
BI_RGB = 0
HWND_TOPMOST = wintypes.HWND(-1)

MENU_REFRESH = 1001
MENU_TOGGLE_STARTUP = 1002
MENU_OPEN_LOGS = 1003
MENU_EXIT = 1004
HOVER_WIDTH = 340
HOVER_HEIGHT = 106
HOVER_GAP = 16
UI_FONT = "Segoe UI Variable Text"

HICON = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p
HMENU = ctypes.c_void_p
HBRUSH = ctypes.c_void_p
HCURSOR = ctypes.c_void_p
HDC = ctypes.c_void_p
HGDIOBJ = ctypes.c_void_p
HBITMAP = ctypes.c_void_p
HRGN = ctypes.c_void_p
LRESULT = ctypes.c_ssize_t
LPVOID = ctypes.c_void_p

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hWnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", HICON),
    ]


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


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = HINSTANCE

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    HMENU,
    HINSTANCE,
    LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = LRESULT
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT), wintypes.BOOL]
user32.InvalidateRect.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, LPVOID]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.KillTimer.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.TrackPopupMenu.argtypes = [
    HMENU,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    ctypes.POINTER(RECT),
]
user32.TrackPopupMenu.restype = wintypes.UINT
user32.CreatePopupMenu.restype = HMENU
user32.AppendMenuW.argtypes = [HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL
user32.DestroyMenu.argtypes = [HMENU]
user32.DestroyMenu.restype = wintypes.BOOL
user32.LoadIconW.argtypes = [HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = HICON
user32.LoadCursorW.argtypes = [HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = HCURSOR
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = HICON
user32.DestroyIcon.argtypes = [HICON]
user32.DestroyIcon.restype = wintypes.BOOL
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, LPVOID, wintypes.UINT]
user32.SystemParametersInfoW.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.FillRect.argtypes = [HDC, ctypes.POINTER(RECT), HBRUSH]
user32.FillRect.restype = ctypes.c_int
user32.DrawTextW.argtypes = [HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = HBRUSH
gdi32.CreateDIBSection.argtypes = [
    HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_void_p,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, LPVOID]
gdi32.CreateBitmap.restype = HBITMAP
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.CreateRoundRectRgn.restype = HRGN
gdi32.FillRgn.argtypes = [HDC, HRGN, HBRUSH]
gdi32.FillRgn.restype = wintypes.BOOL

dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, LPVOID, wintypes.DWORD]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

gdiplus = ctypes.WinDLL("gdiplus", use_last_error=True)


class GDIPLUS_STARTUP_INPUT(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", wintypes.UINT),
        ("DebugEventCallback", LPVOID),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]


gdiplus.GdiplusStartup.argtypes = [
    ctypes.POINTER(ctypes.c_size_t),
    ctypes.POINTER(GDIPLUS_STARTUP_INPUT),
    LPVOID,
]
gdiplus.GdiplusStartup.restype = ctypes.c_int
gdiplus.GdipCreateFromHDC.argtypes = [HDC, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateFromHDC.restype = ctypes.c_int
gdiplus.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetSmoothingMode.restype = ctypes.c_int
gdiplus.GdipCreateSolidFill.argtypes = [wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateSolidFill.restype = ctypes.c_int
gdiplus.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteBrush.restype = ctypes.c_int
gdiplus.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreatePath.restype = ctypes.c_int
gdiplus.GdipAddPathArc.argtypes = [
    ctypes.c_void_p,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
]
gdiplus.GdipAddPathArc.restype = ctypes.c_int
gdiplus.GdipAddPathLine.argtypes = [
    ctypes.c_void_p,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
    ctypes.c_float,
]
gdiplus.GdipAddPathLine.restype = ctypes.c_int
gdiplus.GdipClosePathFigure.argtypes = [ctypes.c_void_p]
gdiplus.GdipClosePathFigure.restype = ctypes.c_int
gdiplus.GdipFillPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
gdiplus.GdipFillPath.restype = ctypes.c_int
gdiplus.GdipDeletePath.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeletePath.restype = ctypes.c_int
gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteGraphics.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.CreateFontW.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.LPCWSTR,
]
gdi32.CreateFontW.restype = HGDIOBJ
gdi32.SelectObject.argtypes = [HDC, HGDIOBJ]
gdi32.SelectObject.restype = HGDIOBJ
gdi32.SetTextColor.argtypes = [HDC, wintypes.COLORREF]
gdi32.SetTextColor.restype = wintypes.COLORREF
gdi32.SetBkMode.argtypes = [HDC, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int


def _resource_id(value: int) -> wintypes.LPCWSTR:
    return ctypes.cast(ctypes.c_void_p(value), wintypes.LPCWSTR)


def _rgb(red: int, green: int, blue: int) -> int:
    return red | (green << 8) | (blue << 16)


def _fill_round_rect(hdc: HDC, rect: RECT, radius: int, color: tuple[int, int, int]) -> None:
    region = gdi32.CreateRoundRectRgn(
        rect.left,
        rect.top,
        rect.right + 1,
        rect.bottom + 1,
        radius,
        radius,
    )
    brush = gdi32.CreateSolidBrush(_rgb(*color))
    if region and brush:
        gdi32.FillRgn(hdc, region, brush)
    if region:
        gdi32.DeleteObject(region)
    if brush:
        gdi32.DeleteObject(brush)


_gdiplus_token = ctypes.c_size_t(0)
_gdiplus_ready = False


def _ensure_gdiplus() -> bool:
    global _gdiplus_ready
    if _gdiplus_ready:
        return True
    startup = GDIPLUS_STARTUP_INPUT(1, None, False, False)
    _gdiplus_ready = gdiplus.GdiplusStartup(ctypes.byref(_gdiplus_token), ctypes.byref(startup), None) == 0
    return _gdiplus_ready


def _fill_round_rect_antialiased(hdc: HDC, rect: RECT, radius: float, color: tuple[int, int, int]) -> bool:
    if not _ensure_gdiplus():
        return False
    graphics = ctypes.c_void_p()
    if gdiplus.GdipCreateFromHDC(hdc, ctypes.byref(graphics)) != 0:
        return False
    brush = ctypes.c_void_p()
    path = ctypes.c_void_p()
    try:
        gdiplus.GdipSetSmoothingMode(graphics, 4)  # SmoothingModeAntiAlias
        if gdiplus.GdipCreateSolidFill(
            (255 << 24) | (color[0] << 16) | (color[1] << 8) | color[2],
            ctypes.byref(brush),
        ) != 0:
            return False
        if gdiplus.GdipCreatePath(0, ctypes.byref(path)) != 0:
            return False
        left = float(rect.left)
        top = float(rect.top)
        width = float(rect.right - rect.left)
        height = float(rect.bottom - rect.top)
        diameter = min(float(radius * 2), width, height)
        right = left + width
        bottom = top + height
        gdiplus.GdipAddPathArc(path, right - diameter, top, diameter, diameter, 270.0, 90.0)
        gdiplus.GdipAddPathArc(path, right - diameter, bottom - diameter, diameter, diameter, 0.0, 90.0)
        gdiplus.GdipAddPathArc(path, left, bottom - diameter, diameter, diameter, 90.0, 90.0)
        gdiplus.GdipAddPathArc(path, left, top, diameter, diameter, 180.0, 90.0)
        gdiplus.GdipClosePathFigure(path)
        return gdiplus.GdipFillPath(graphics, brush, path) == 0
    finally:
        if path:
            gdiplus.GdipDeletePath(path)
        if brush:
            gdiplus.GdipDeleteBrush(brush)
        if graphics:
            gdiplus.GdipDeleteGraphics(graphics)


def _apply_win11_window_style(hwnd: wintypes.HWND) -> None:
    corner_preference = ctypes.c_int(2)  # DWMWCP_ROUND
    dark_mode = ctypes.c_int(1)
    dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner_preference), ctypes.sizeof(corner_preference))
    dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))


def _hover_position(
    cursor_x: int,
    cursor_y: int,
    work_area: RECT,
    *,
    width: int = HOVER_WIDTH,
    height: int = HOVER_HEIGHT,
    gap: int = HOVER_GAP,
) -> tuple[int, int]:
    """Place the hover card beside the cursor without covering its anchor icon."""

    min_x = work_area.left + 8
    max_x = max(min_x, work_area.right - width - 8)
    min_y = work_area.top + 8
    max_y = max(min_y, work_area.bottom - height - 8)

    left_x = cursor_x - width - gap
    right_x = cursor_x + gap
    if left_x >= min_x:
        x = left_x
    elif right_x <= max_x:
        x = right_x
    else:
        x = max(min_x, min(cursor_x - width // 2, max_x))

    above_y = cursor_y - height - gap
    below_y = cursor_y + gap
    if above_y >= min_y:
        y = above_y
    elif below_y <= max_y:
        y = below_y
    else:
        y = max(min_y, min(cursor_y - height // 2, max_y))

    return x, y


def _startup_file_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise OSError("APPDATA is unavailable")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "CodexQuotaMonitor.vbs"


def _vbscript_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _startup_script_text() -> str:
    if getattr(sys, "frozen", False):
        command_parts = [Path(sys.executable)]
    else:
        command_parts = [Path(sys.executable), Path(__file__).resolve().with_name("main.py")]
    command = " ".join(_vbscript_string(str(part)) for part in command_parts)
    return (
        'Set shell = CreateObject("WScript.Shell")\n'
        f"shell.Run {_vbscript_string(command)}, 0, False\n"
    )


def _remaining_value(window: object | None) -> float | None:
    if window is None:
        return None
    value = getattr(window, "remaining_percent", None)
    return float(value) if value is not None else None


def _quota_accent(snapshot: QuotaSnapshot) -> tuple[int, int, int]:
    values = [
        value
        for value in (
            _remaining_value(snapshot.primary),
            _remaining_value(snapshot.weekly),
        )
        if value is not None
    ]
    remaining = min(values) if values else 50.0
    if remaining < 20.0:
        return 205, 91, 91
    if remaining < 50.0:
        return 211, 160, 72
    return 76, 181, 145


def _create_quota_icon(snapshot: QuotaSnapshot) -> HICON | None:
    """Create a small flat C/gauge icon without external image assets."""

    size = 32
    accent = _quota_accent(snapshot)
    inner = (39, 51, 64)
    white = (242, 244, 246)
    pixels = (ctypes.c_uint32 * (size * size))()

    def pixel(red: int, green: int, blue: int, alpha: int = 255) -> int:
        return blue | (green << 8) | (red << 16) | (alpha << 24)

    for y in range(size):
        for x in range(size):
            dx = x - 15.5
            dy = y - 15.5
            distance = math.sqrt(dx * dx + dy * dy)
            if distance > 16.4:
                pixels[y * size + x] = 0
            else:
                if distance >= 12.0:
                    color = accent
                elif distance >= 11.2:
                    blend = (distance - 11.2) / 0.8
                    color = tuple(int(inner[index] * (1.0 - blend) + accent[index] * blend) for index in range(3))
                else:
                    color = inner
                alpha = 255 if distance <= 15.2 else int(max(0.0, min(1.0, (16.4 - distance) / 1.2)) * 255)
                pixels[y * size + x] = pixel(*color, alpha)

    # A compact white C glyph remains legible at the 16px tray size.
    glyph = ("1111", "1000", "1000", "1000", "1111")
    for row, pattern in enumerate(glyph):
        for column, value in enumerate(pattern):
            if value != "1":
                continue
            for yy in range(2):
                for xx in range(2):
                    x = 12 + column * 2 + xx
                    y = 11 + row * 2 + yy
                    pixels[y * size + x] = pixel(*white)

    bitmap_info = BITMAPINFO(
        bmiHeader=BITMAPINFOHEADER(
            biSize=ctypes.sizeof(BITMAPINFOHEADER),
            biWidth=size,
            biHeight=-size,
            biPlanes=1,
            biBitCount=32,
            biCompression=BI_RGB,
        )
    )
    bits = ctypes.c_void_p()
    color_bitmap = gdi32.CreateDIBSection(
        None,
        ctypes.byref(bitmap_info),
        DIB_RGB_COLORS,
        ctypes.byref(bits),
        None,
        0,
    )
    if not color_bitmap or not bits.value:
        return None

    ctypes.memmove(bits.value, pixels, ctypes.sizeof(pixels))
    mask_bitmap = gdi32.CreateBitmap(size, size, 1, 1, None)
    if not mask_bitmap:
        gdi32.DeleteObject(color_bitmap)
        return None

    icon_info = ICONINFO(fIcon=1, xHotspot=0, yHotspot=0, hbmMask=mask_bitmap, hbmColor=color_bitmap)
    icon = user32.CreateIconIndirect(ctypes.byref(icon_info))
    gdi32.DeleteObject(color_bitmap)
    gdi32.DeleteObject(mask_bitmap)
    return icon or None


class WindowsTrayApp:
    """Message-loop based tray application with a small optional status window."""

    def __init__(
        self,
        scanner: SessionScanner,
        *,
        refresh_interval: float = 3.0,
    ) -> None:
        self.scanner = scanner
        self.refresh_interval = max(1.0, refresh_interval)
        self.tray_hwnd: wintypes.HWND | None = None
        self.hover_hwnd: wintypes.HWND | None = None
        self.hover_visible = False
        self._last_hover_point: POINT | None = None
        self.tray_available = False
        self.tray_error: int | None = None
        self._icon_handle: HICON | None = None
        self._owns_icon = False
        self._hinstance = kernel32.GetModuleHandleW(None)
        self._registered_classes: list[str] = []
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._refresh_lock = threading.Lock()
        self._refresh_requested = False
        self._pending_lock = threading.Lock()
        self._pending_snapshot: QuotaSnapshot | None = None
        self._pending_error: str | None = None
        self._worker: threading.Thread | None = None
        self._snapshot = QuotaSnapshot(None, None, None, 0, 0, 0, ())
        self._scan_error: str | None = None
        self._tray_callback = WNDPROC(self._tray_window_proc)
        self._hover_callback = WNDPROC(self._hover_window_proc)
        self._notify_icon = NOTIFYICONDATAW()

    def run(self, *, smoke_seconds: float | None = None) -> int:
        smoke_timer: threading.Timer | None = None
        try:
            self._register_classes()
            self._create_tray_window()
            self._create_hover_window()
            self._worker = threading.Thread(target=self._scan_worker, name="quota-scan", daemon=True)
            self._worker.start()

            deadline = time.monotonic() + smoke_seconds if smoke_seconds is not None else None
            if smoke_seconds is not None:
                smoke_timer = threading.Timer(
                    max(0.0, smoke_seconds),
                    self._request_stop,
                )
                smoke_timer.daemon = True
                smoke_timer.start()
            message = MSG()
            while not self._stop_event.is_set():
                processed_messages = 0
                while (
                    not self._stop_event.is_set()
                    and processed_messages < 100
                    and user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE)
                ):
                    processed_messages += 1
                    if message.message == 0x0012:  # WM_QUIT
                        self._stop_event.set()
                        break
                    user32.TranslateMessage(ctypes.byref(message))
                    user32.DispatchMessageW(ctypes.byref(message))
                    if deadline is not None and time.monotonic() >= deadline:
                        self._stop_event.set()
                        self._wake_event.set()
                        break
                if deadline is not None and time.monotonic() >= deadline:
                    self._stop_event.set()
                    self._wake_event.set()
                    break
                time.sleep(0.05)
            return 0
        finally:
            if smoke_timer is not None:
                smoke_timer.cancel()
            self._cleanup()

    def _request_stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self.tray_hwnd:
            user32.PostMessageW(self.tray_hwnd, WM_CLOSE, 0, 0)

    def _register_classes(self) -> None:
        self._register_class(TRAY_CLASS, self._tray_callback)
        self._register_class(HOVER_CLASS, self._hover_callback)

    def _register_class(self, class_name: str, callback: WNDPROC) -> None:
        icon = user32.LoadIconW(None, _resource_id(32512))
        cursor = user32.LoadCursorW(None, _resource_id(32512))
        window_class = WNDCLASSEXW(
            cbSize=ctypes.sizeof(WNDCLASSEXW),
            style=0,
            lpfnWndProc=callback,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=self._hinstance,
            hIcon=icon,
            hCursor=cursor,
            hbrBackground=None,
            lpszMenuName=None,
            lpszClassName=class_name,
            hIconSm=icon,
        )
        atom = user32.RegisterClassExW(ctypes.byref(window_class))
        if not atom:
            error = ctypes.get_last_error()
            if error != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(error)
        self._registered_classes.append(class_name)

    def _create_tray_window(self) -> None:
        self.tray_hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW,
            TRAY_CLASS,
            APP_NAME,
            WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            self._hinstance,
            None,
        )
        if not self.tray_hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

        icon = _create_quota_icon(self._snapshot)
        if icon:
            self._icon_handle = icon
            self._owns_icon = True
        else:
            icon = user32.LoadIconW(None, _resource_id(32516))  # IDI_INFORMATION fallback
        self._notify_icon = NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(NOTIFYICONDATAW),
            hWnd=self.tray_hwnd,
            uID=1,
            uFlags=NIF_MESSAGE | NIF_ICON,
            uCallbackMessage=WM_TRAY_CALLBACK,
            hIcon=icon,
        )
        if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._notify_icon)):
            self.tray_available = True
        else:
            # Some managed/remote Windows desktops have no notification area.
            # Keep the hidden message window so hover state can be cleaned up.
            self.tray_available = False
            self.tray_error = ctypes.get_last_error()
        user32.SetTimer(self.tray_hwnd, TIMER_HOVER, 100, None)

    def _create_hover_window(self) -> None:
        self.hover_hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_LAYERED,
            HOVER_CLASS,
            APP_NAME,
            WS_POPUP,
            0,
            0,
            HOVER_WIDTH,
            HOVER_HEIGHT,
            None,
            None,
            self._hinstance,
            None,
        )
        if self.hover_hwnd:
            user32.SetLayeredWindowAttributes(self.hover_hwnd, 0, 248, LWA_ALPHA)
            _apply_win11_window_style(self.hover_hwnd)

    def _scan_worker(self) -> None:
        force_scan = True
        refresh_cycles = 0
        force_refresh_cycles = max(1, round(30.0 / self.refresh_interval))
        previous: QuotaSnapshot | None = None
        while not self._stop_event.is_set():
            with self._refresh_lock:
                if self._refresh_requested:
                    force_scan = True
                    self._refresh_requested = False

            try:
                snapshot = self.scanner.scan(force=force_scan)
                error = None
            except Exception as exc:  # Keep the tray alive if a file disappears mid-scan.
                snapshot = None
                error = f"{type(exc).__name__}: {exc}"

            if snapshot is not None and snapshot is not previous:
                previous = snapshot
                with self._pending_lock:
                    self._pending_snapshot = snapshot
                    self._pending_error = None
                if self.tray_hwnd:
                    user32.PostMessageW(self.tray_hwnd, WM_REFRESH_READY, 0, 0)
            elif error is not None:
                with self._pending_lock:
                    self._pending_error = error
                if self.tray_hwnd:
                    user32.PostMessageW(self.tray_hwnd, WM_REFRESH_READY, 0, 0)

            refresh_cycles = 0 if force_scan else refresh_cycles + 1
            force_scan = False
            self._wake_event.wait(self.refresh_interval)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            force_scan = refresh_cycles >= force_refresh_cycles

    def _apply_pending(self) -> None:
        with self._pending_lock:
            snapshot = self._pending_snapshot
            error = self._pending_error
            self._pending_snapshot = None
            self._pending_error = None
        if snapshot is not None:
            self._snapshot = snapshot
        self._scan_error = error
        self._update_notify_icon()
        if self.hover_hwnd:
            user32.InvalidateRect(self.hover_hwnd, None, True)

    def _update_notify_icon(self) -> None:
        icon = _create_quota_icon(self._snapshot)
        old_icon = None
        if icon:
            old_icon = self._icon_handle if self._owns_icon else None
            self._icon_handle = icon
            self._owns_icon = True
            self._notify_icon.hIcon = icon
        self._notify_icon.szTip = ""
        if self.tray_hwnd and self.tray_available:
            self._notify_icon.uFlags = NIF_MESSAGE | NIF_ICON
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._notify_icon))
        if old_icon:
            user32.DestroyIcon(old_icon)

    def _show_hover_from_cursor(self) -> None:
        if not self.hover_hwnd:
            return
        cursor = POINT()
        if user32.GetCursorPos(ctypes.byref(cursor)):
            self._last_hover_point = POINT(cursor.x, cursor.y)
            width, height = HOVER_WIDTH, HOVER_HEIGHT
            work_area = RECT()
            if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work_area), 0):
                x, y = _hover_position(cursor.x, cursor.y, work_area, width=width, height=height)
            else:
                fallback_area = RECT(0, 0, 0x7FFFFFFF, 0x7FFFFFFF)
                x, y = _hover_position(cursor.x, cursor.y, fallback_area, width=width, height=height)
            user32.SetWindowPos(
                self.hover_hwnd,
                HWND_TOPMOST,
                x,
                y,
                width,
                height,
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            self.hover_visible = True
            user32.InvalidateRect(self.hover_hwnd, None, True)

    def _hide_hover(self) -> None:
        if self.hover_hwnd and self.hover_visible:
            user32.ShowWindow(self.hover_hwnd, SW_HIDE)
        self.hover_visible = False
        self._last_hover_point = None

    def _check_hover(self) -> None:
        if not self.hover_hwnd or not self.hover_visible or self._last_hover_point is None:
            return
        cursor = POINT()
        if not user32.GetCursorPos(ctypes.byref(cursor)):
            return
        hover_rect = RECT()
        if user32.GetWindowRect(self.hover_hwnd, ctypes.byref(hover_rect)):
            if (
                hover_rect.left <= cursor.x <= hover_rect.right
                and hover_rect.top <= cursor.y <= hover_rect.bottom
            ):
                return
        if abs(cursor.x - self._last_hover_point.x) > 20 or abs(cursor.y - self._last_hover_point.y) > 20:
            self._hide_hover()

    def _tray_window_proc(
        self,
        hwnd: wintypes.HWND,
        message: int,
        wparam: int,
        lparam: int,
    ) -> int:
        try:
            if message == WM_REFRESH_READY:
                self._apply_pending()
                return 0
            if message == WM_TIMER and wparam == TIMER_HOVER:
                self._check_hover()
                return 0
            if message == WM_TRAY_CALLBACK:
                if lparam == WM_MOUSEMOVE:
                    self._show_hover_from_cursor()
                elif lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._hide_hover()
                    self._show_context_menu()
                return 0
            if message == WM_COMMAND:
                self._handle_menu_command(wparam & 0xFFFF)
                return 0
            if message == WM_CLOSE:
                self._stop_event.set()
                self._wake_event.set()
                return 0
            if message == WM_DESTROY:
                return 0
        except Exception:
            # Never let an exception escape a ctypes callback into user32.
            return 0
        return int(user32.DefWindowProcW(hwnd, message, wparam, lparam))

    def _hover_window_proc(
        self,
        hwnd: wintypes.HWND,
        message: int,
        wparam: int,
        lparam: int,
    ) -> int:
        try:
            if message == WM_PAINT:
                self._paint_hover(hwnd)
                return 0
            if message == WM_ERASEBKGND:
                return 1
            if message == WM_NCHITTEST:
                return HTTRANSPARENT
            if message == WM_CLOSE:
                self._hide_hover()
                return 0
        except Exception:
            return 0
        return int(user32.DefWindowProcW(hwnd, message, wparam, lparam))

    def _paint_hover(self, hwnd: wintypes.HWND) -> None:
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        row_font = None
        footer_font = None
        try:
            client = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client))
            background = gdi32.CreateSolidBrush(_rgb(31, 36, 44))
            user32.FillRect(hdc, ctypes.byref(client), background)
            gdi32.DeleteObject(background)

            gdi32.SetBkMode(hdc, TRANSPARENT)
            row_font = gdi32.CreateFontW(
                -13,
                0,
                0,
                0,
                FW_SEMIBOLD,
                0,
                0,
                0,
                DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS,
                CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY,
                DEFAULT_PITCH | FF_DONTCARE,
                UI_FONT,
            )
            footer_font = gdi32.CreateFontW(
                -11,
                0,
                0,
                0,
                400,
                0,
                0,
                0,
                DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS,
                CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY,
                DEFAULT_PITCH | FF_DONTCARE,
                UI_FONT,
            )

            self._paint_quota_row(hdc, row_font, 17, "H", self._snapshot.primary)
            self._paint_quota_row(hdc, row_font, 46, "W", self._snapshot.weekly)

            old_font = gdi32.SelectObject(hdc, footer_font)
            gdi32.SetTextColor(hdc, _rgb(155, 163, 173))
            reset_5h = format_reset(self._snapshot.primary.resets_at if self._snapshot.primary else None)
            reset_week = format_reset(self._snapshot.weekly.resets_at if self._snapshot.weekly else None)
            footer = f"Updated {format_updated(self._snapshot.updated_at)}  |  Reset {reset_5h} / {reset_week}"
            if self._scan_error:
                footer = f"Scan error: {self._scan_error}"
            footer_rect = RECT(10, 83, 330, 102)
            user32.DrawTextW(
                hdc,
                footer,
                -1,
                ctypes.byref(footer_rect),
                DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX,
            )
            gdi32.SelectObject(hdc, old_font)
        finally:
            if row_font:
                gdi32.DeleteObject(row_font)
            if footer_font:
                gdi32.DeleteObject(footer_font)
            user32.EndPaint(hwnd, ctypes.byref(paint))

    def _paint_quota_row(
        self,
        hdc: HDC,
        font: HGDIOBJ,
        y: int,
        label: str,
        window: object | None,
    ) -> None:
        old_font = gdi32.SelectObject(hdc, font)
        gdi32.SetTextColor(hdc, _rgb(223, 227, 232))
        label_rect = RECT(16, y, 46, y + 22)
        user32.DrawTextW(hdc, label, -1, ctypes.byref(label_rect), DT_LEFT | DT_VCENTER | DT_SINGLELINE)

        bar_rect = RECT(56, y + 6, 258, y + 16)
        if not _fill_round_rect_antialiased(hdc, bar_rect, 5.0, (61, 69, 82)):
            _fill_round_rect(hdc, bar_rect, 5, (61, 69, 82))

        remaining = _remaining_value(window)
        if remaining is not None:
            accent = _quota_accent(
                QuotaSnapshot(
                    primary=window if label == "H" else None,
                    weekly=window if label == "W" else None,
                    updated_at=None,
                    scanned_files=0,
                    rate_limit_records=0,
                    malformed_lines=0,
                    field_names=(),
                )
            )
            fill_right = bar_rect.left + int((bar_rect.right - bar_rect.left) * max(0.0, min(100.0, remaining)) / 100.0)
            fill_rect = RECT(bar_rect.left, bar_rect.top, max(bar_rect.left + 1, fill_right), bar_rect.bottom)
            if not _fill_round_rect_antialiased(hdc, fill_rect, 5.0, accent):
                _fill_round_rect(hdc, fill_rect, 5, accent)
            value_text = f"{remaining:.0f}%"
        else:
            value_text = "--"

        value_rect = RECT(270, y, 328, y + 22)
        gdi32.SetTextColor(hdc, _rgb(244, 246, 248))
        user32.DrawTextW(hdc, value_text, -1, ctypes.byref(value_rect), DT_RIGHT | DT_VCENTER | DT_SINGLELINE)
        gdi32.SelectObject(hdc, old_font)

    def _show_context_menu(self) -> None:
        if not self.tray_hwnd or not self.tray_available:
            return
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            user32.AppendMenuW(menu, MF_STRING, MENU_REFRESH, "刷新")
            startup_label = "关闭开机启动" if self._startup_file_path().is_file() else "开启开机启动"
            user32.AppendMenuW(menu, MF_STRING, MENU_TOGGLE_STARTUP, startup_label)
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, MENU_OPEN_LOGS, "打开 Codex 日志目录")
            user32.AppendMenuW(menu, MF_STRING, MENU_EXIT, "退出")
            cursor = POINT()
            user32.GetCursorPos(ctypes.byref(cursor))
            user32.SetForegroundWindow(self.tray_hwnd)
            command = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                cursor.x,
                cursor.y,
                0,
                self.tray_hwnd,
                None,
            )
            if command:
                self._handle_menu_command(command)
        finally:
            user32.DestroyMenu(menu)

    def _handle_menu_command(self, command: int) -> None:
        if command == MENU_REFRESH:
            with self._refresh_lock:
                self._refresh_requested = True
            self._wake_event.set()
        elif command == MENU_TOGGLE_STARTUP:
            try:
                startup_file = self._startup_file_path()
                if startup_file.is_file():
                    startup_file.unlink()
                else:
                    startup_file.parent.mkdir(parents=True, exist_ok=True)
                    startup_file.write_text(_startup_script_text(), encoding="utf-16")
                self._scan_error = None
            except OSError as exc:
                self._scan_error = f"startup: {exc}"
            self._update_notify_icon()
        elif command == MENU_OPEN_LOGS:
            try:
                os.startfile(str(self.scanner.sessions_dir))
            except OSError:
                self._scan_error = f"cannot open {self.scanner.sessions_dir}"
                self._update_notify_icon()
        elif command == MENU_EXIT:
            self._stop_event.set()
            self._wake_event.set()

    @staticmethod
    def _startup_file_path() -> Path:
        return _startup_file_path()

    def _cleanup(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None

        if self.tray_hwnd:
            user32.KillTimer(self.tray_hwnd, TIMER_HOVER)
        if self.hover_hwnd:
            self._hide_hover()
            user32.DestroyWindow(self.hover_hwnd)
            self.hover_hwnd = None
        if self.tray_hwnd:
            if self.tray_available:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._notify_icon))
            user32.DestroyWindow(self.tray_hwnd)
            self.tray_hwnd = None
        if self._icon_handle and self._owns_icon:
            user32.DestroyIcon(self._icon_handle)
            self._icon_handle = None
            self._owns_icon = False
        for class_name in reversed(self._registered_classes):
            user32.UnregisterClassW(class_name, self._hinstance)
        self._registered_classes.clear()
