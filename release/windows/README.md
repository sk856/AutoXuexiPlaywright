# Windows release build

`release/windows/ui-copy-source/` is the versioned source for the desktop
Qt dashboard delivered in the Windows archive. It intentionally mirrors the
maintained `ui-copy` implementation rather than the incomplete experimental UI
under `src/autoxuexiplaywright/ui/qt`.

## Prerequisites

- 64-bit Python with the runtime dependencies installed, including PyInstaller.
- A Playwright Firefox payload installed locally:

  ```powershell
  python -m playwright install firefox
  ```

  Set `PLAYWRIGHT_BROWSERS_PATH` if the browser payload is stored outside
  `%LOCALAPPDATA%\ms-playwright`.

## Build

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\release\windows\build-windows.ps1 -Version 4.0.3 -Python 'D:\Program Files\Python311\python.exe'
```

The command produces a folder and ZIP under `dist-release/`. The folder contains
only `AutoXuexiPlaywright.exe` and `_internal/` at its root. Before creating the
archive, the script rejects `config.json`, cookies, and logs so user settings,
login state, and API keys never enter a release asset.
