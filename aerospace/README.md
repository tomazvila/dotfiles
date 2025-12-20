# AeroSpace - Tiling Window Manager for macOS

AeroSpace is an i3-like tiling window manager for macOS. It automatically arranges windows in a non-overlapping layout, maximizing screen real estate.

**Website:** https://nikitabobko.github.io/AeroSpace/guide

## Why AeroSpace?

- No SIP (System Integrity Protection) changes required
- Built-in hotkey system (no separate skhd needed)
- i3-like configuration (familiar for Linux users)
- Virtual workspaces with instant switching (no macOS animation lag)
- Single binary, simple setup

## Keybindings

### Window Focus (vim-style)
| Key | Action |
|-----|--------|
| `Alt + h` | Focus left |
| `Alt + j` | Focus down |
| `Alt + k` | Focus up |
| `Alt + l` | Focus right |

### Move Windows
| Key | Action |
|-----|--------|
| `Alt + Shift + h` | Move window left |
| `Alt + Shift + j` | Move window down |
| `Alt + Shift + k` | Move window up |
| `Alt + Shift + l` | Move window right |

### Resize Windows
| Key | Action |
|-----|--------|
| `Alt + -` | Shrink window |
| `Alt + =` | Grow window |

### Layout Controls
| Key | Action |
|-----|--------|
| `Alt + \` | Split horizontally |
| `Alt + Shift + \` | Split vertically |
| `Alt + ,` | Tiles layout (BSP) |
| `Alt + .` | Accordion layout (stacking) |
| `Alt + f` | Toggle fullscreen |
| `Alt + Shift + f` | Toggle floating |

### Workspaces
| Key | Action |
|-----|--------|
| `Alt + 1-9` | Switch to workspace 1-9 |
| `Alt + Shift + 1-9` | Move window to workspace 1-9 |
| `Alt + Tab` | Switch to previous workspace |
| `Alt + Shift + Tab` | Move workspace to next monitor |

### Service Mode
Press `Alt + Shift + ;` to enter service mode for less common actions:

| Key | Action |
|-----|--------|
| `Esc` | Exit service mode |
| `r` | Flatten workspace tree |
| `f` | Toggle floating |
| `Backspace` | Close all windows except current |
| `Alt + Shift + =` | Balance window sizes |
| `Alt + Shift + h/j/k/l` | Join with adjacent window |

## Useful Commands

```bash
# Check if AeroSpace is running
aerospace list-workspaces --all

# Reload configuration
aerospace reload-config

# List all windows
aerospace list-windows --all

# Get current workspace
aerospace list-workspaces --focused
```

## Configuration

The configuration file is managed by nix and placed at `~/.aerospace.toml`.

To customize, edit `aerospace/default.nix` and rebuild:

```bash
darwin-rebuild switch --flake .#mac
```

## Floating Windows

Some apps are configured to always float:
- System Settings
- Calculator
- Finder copy/move dialogs

To add more apps, find their bundle ID:

```bash
osascript -e 'id of app "AppName"'
```

Then add a rule in `default.nix`.
