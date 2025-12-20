# Tmux Configuration

Declarative tmux configuration using home-manager.

## Getting Started

```bash
# Start tmux
tmux

# Start with a named session
tmux new -s myproject

# Attach to existing session
tmux attach -t myproject

# List sessions
tmux ls
```

## Keybindings

Prefix key: `Ctrl-a`

### Sessions
| Key | Action |
|-----|--------|
| `C-a d` | Detach from session |
| `C-a $` | Rename session |
| `C-a s` | List/switch sessions |

### Windows
| Key | Action |
|-----|--------|
| `C-a c` | Create new window |
| `C-a ,` | Rename window |
| `C-a n` | Next window |
| `C-a p` | Previous window |
| `C-a 1-9` | Switch to window by number |
| `C-a &` | Close window |

### Panes
| Key | Action |
|-----|--------|
| `C-a |` | Split horizontally |
| `C-a -` | Split vertically |
| `C-a h/j/k/l` | Navigate panes (vim-style) |
| `C-a C-h/j/k/l` | Resize panes |
| `C-a x` | Close pane |
| `C-a z` | Toggle pane zoom |
| `C-a !` | Convert pane to window |

### Copy Mode (Vi-style)
| Key | Action |
|-----|--------|
| `C-a [` | Enter copy mode |
| `v` | Start selection |
| `y` | Copy selection |
| `C-a ]` | Paste |

### Other
| Key | Action |
|-----|--------|
| `C-a r` | Reload config |
| `C-a ?` | List keybindings |

## Plugins

### Catppuccin Theme
Mocha flavor matching neovim theme. Status bar shows session name and time.

### Resurrect
Save and restore tmux sessions.
- `C-a C-s` - Save session
- `C-a C-r` - Restore session

Sessions saved to `~/.tmux/resurrect/`

### Continuum
Automatic session saving every 10 minutes. Sessions auto-restore when tmux starts.

## Tips

- Mouse is enabled - click to select panes, scroll to browse history
- New windows/panes open in current directory
- Base index is 1 (windows numbered 1, 2, 3...)
- History limit: 50,000 lines
