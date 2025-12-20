# My Neovim Configuration

A fully declarative Neovim configuration built with [NixVim](https://github.com/nix-community/nixvim).

## Quick Start

### Run without installing
```bash
nix run ~/.config/neovim
# or from GitHub (once pushed):
nix run github:yourusername/dotfiles?dir=neovim
```

### Test the configuration
```bash
cd ~/.config/neovim
nix run
```

### Update NixVim and plugins
```bash
cd ~/.config/neovim
nix flake update
```

---

## Installation (Integration with nix-darwin)

### 1. Add to your main flake.nix inputs:
```nix
inputs.neovim.url = "path:/Users/lilvilla/.config/neovim";
# or from GitHub:
# inputs.neovim.url = "github:yourusername/dotfiles?dir=neovim";
```

### 2. Pass inputs to home-manager:
```nix
home-manager.users.lilvilla = import ./home.nix;
# becomes:
home-manager.users.lilvilla = { pkgs, ... }: {
  imports = [ ./home.nix ];
};
home-manager.extraSpecialArgs = { inherit inputs; };
```

### 3. Add to home.nix:
```nix
{ pkgs, inputs, ... }: {
  home.packages = [
    inputs.neovim.packages.${pkgs.system}.default
  ];
}
```

### 4. Rebuild:
```bash
darwin-rebuild switch --flake /etc/nix-darwin
```

---

## Keybindings

Leader key: `<Space>`

### General

| Key | Action |
|-----|--------|
| `<Space>w` | Save file |
| `<Space>q` | Quit |
| `<Space>x` | Save and quit |
| `<Esc>` | Clear search highlight |

### Navigation

| Key | Action |
|-----|--------|
| `<C-h/j/k/l>` | Move between windows |
| `<C-d>` | Scroll down (centered) |
| `<C-u>` | Scroll up (centered) |
| `<S-h>` | Previous buffer |
| `<S-l>` | Next buffer |
| `n/N` | Next/prev search result (centered) |

### Window Splits

| Key | Action |
|-----|--------|
| `<Space>sv` | Split vertical |
| `<Space>sh` | Split horizontal |
| `<Space>se` | Equal split sizes |
| `<Space>sx` | Close split |

### Buffers

| Key | Action |
|-----|--------|
| `<Space>bd` | Delete buffer |
| `<S-h>` | Previous buffer |
| `<S-l>` | Next buffer |

### File Explorer (Neo-tree)

| Key | Action |
|-----|--------|
| `<Space>e` | Toggle file explorer |
| `<Space>o` | Focus file explorer |

Inside Neo-tree:
- `a` - Add file/folder
- `d` - Delete
- `r` - Rename
- `c` - Copy
- `m` - Move
- `y` - Copy name
- `Y` - Copy path
- `<CR>` - Open file

### Telescope (Fuzzy Finder)

| Key | Action |
|-----|--------|
| `<Space>ff` | Find files |
| `<Space>fg` | Live grep (search text) |
| `<Space>fb` | Find buffers |
| `<Space>fh` | Help tags |
| `<Space>fo` | Recent files |
| `<Space>fw` | Grep word under cursor |
| `<Space>fd` | Diagnostics |
| `<Space>fs` | Document symbols |
| `<Space>fr` | Resume last search |

Inside Telescope:
- `<C-j/k>` - Move up/down
- `<C-n/p>` - Move up/down (alternative)
- `<CR>` - Select
- `<C-x>` - Open in horizontal split
- `<C-v>` - Open in vertical split
- `<Esc>` - Close

### Git (Telescope)

| Key | Action |
|-----|--------|
| `<Space>gc` | Git commits |
| `<Space>gb` | Git branches |
| `<Space>gs` | Git status |

### LSP (Language Server)

| Key | Action |
|-----|--------|
| `gd` | Go to definition |
| `gD` | Go to declaration |
| `gi` | Go to implementation |
| `gr` | Find references |
| `K` | Hover documentation |
| `<Space>ca` | Code actions |
| `<Space>rn` | Rename symbol |
| `<Space>D` | Type definition |
| `<Space>ds` | Show diagnostics float |
| `<Space>cf` | Format code |
| `[d` | Previous diagnostic |
| `]d` | Next diagnostic |

### Debugger (DAP)

| Key | Action |
|-----|--------|
| `<Space>dc` | Continue/Start debugging |
| `<Space>do` | Step over |
| `<Space>di` | Step into |
| `<Space>du` | Step out |
| `<Space>db` | Toggle breakpoint |
| `<Space>dB` | Conditional breakpoint |
| `<Space>dr` | Open REPL |
| `<Space>dl` | Run last debug config |
| `<Space>dt` | Toggle DAP UI |

### Trouble (Diagnostics Panel)

| Key | Action |
|-----|--------|
| `<Space>xx` | Toggle diagnostics |
| `<Space>xX` | Buffer diagnostics only |
| `<Space>cs` | Symbols |
| `<Space>xL` | Location list |
| `<Space>xQ` | Quickfix list |

### Editing

| Key | Action |
|-----|--------|
| `gc` (visual) | Toggle comment |
| `gcc` | Toggle line comment |
| `J` (visual) | Move line down |
| `K` (visual) | Move line up |
| `<Space>p` (visual) | Paste without yanking |
| `<Space>y` | Yank to system clipboard |
| `<Space>d` | Delete without yanking |

### Surround

| Key | Action |
|-----|--------|
| `ys{motion}{char}` | Add surround |
| `ds{char}` | Delete surround |
| `cs{old}{new}` | Change surround |

Examples:
- `ysiw"` - Surround word with quotes
- `ds"` - Delete surrounding quotes
- `cs"'` - Change " to '

### Flash (Jump Navigation)

| Key | Action |
|-----|--------|
| `s` | Flash jump |
| `S` | Flash treesitter select |

---

## Installed Plugins

### Core
| Plugin | Description |
|--------|-------------|
| **Treesitter** | Advanced syntax highlighting and code parsing |
| **LSP** | Language server protocol support |
| **nvim-cmp** | Autocompletion engine |
| **LuaSnip** | Snippet engine |
| **Telescope** | Fuzzy finder for files, grep, buffers |
| **Neo-tree** | File explorer sidebar |

### UI
| Plugin | Description |
|--------|-------------|
| **Catppuccin** | Color scheme (mocha variant) |
| **Lualine** | Status line |
| **Which-key** | Keybinding hints popup |
| **Indent-blankline** | Indentation guides |
| **Notify** | Better notification popups |
| **Fidget** | LSP progress indicator |

### Editing
| Plugin | Description |
|--------|-------------|
| **nvim-autopairs** | Auto-close brackets and quotes |
| **Comment.nvim** | Easy commenting with `gc` |
| **nvim-surround** | Add/change/delete surroundings |
| **Flash** | Fast navigation and selection |
| **Illuminate** | Highlight word under cursor |

### Git
| Plugin | Description |
|--------|-------------|
| **Gitsigns** | Git signs in the gutter |
| **Lazygit** | Git UI (open with `:LazyGit`) |

### Debugging
| Plugin | Description |
|--------|-------------|
| **nvim-dap** | Debug Adapter Protocol |
| **dap-ui** | UI for debugger |
| **dap-virtual-text** | Inline debug values |
| **dap-python** | Python debugger adapter |

### Extras
| Plugin | Description |
|--------|-------------|
| **Trouble** | Better diagnostics list |
| **Todo-comments** | Highlight TODO/FIXME/etc |
| **nix.vim** | Nix file support |

---

## LSP Servers

| Language | Server | Features |
|----------|--------|----------|
| TypeScript/JavaScript | ts_ls | Full TS support, auto-imports |
| ESLint | eslint | Linting integration |
| Nix | nixd | Nix expression support |
| Python | pyright | Type checking, completion |
| Scala | metals | Full Scala support |
| Haskell | hls | Haskell Language Server |
| Rust | rust-analyzer | Full Rust support |
| Lua | lua_ls | For Neovim config |
| HTML | html | HTML completion |
| CSS | cssls | CSS completion |
| JSON | jsonls | JSON schemas |
| YAML | yamlls | YAML support |

---

## Adding New Plugins

Edit `flake.nix` and add plugins to the `plugins` section:

```nix
plugins.your-plugin = {
  enable = true;
  settings = {
    # plugin options
  };
};
```

Then rebuild:
```bash
cd ~/.config/neovim
nix flake update  # optional, to update inputs
darwin-rebuild switch --flake /etc/nix-darwin
```

### Finding NixVim options

- [NixVim documentation](https://nix-community.github.io/nixvim/)
- [NixVim options search](https://nix-community.github.io/nixvim/search/)

---

## Troubleshooting

### Check if LSP is running
```vim
:LspInfo
```

### Check Treesitter parsers
```vim
:TSInstallInfo
```

### Health check
```vim
:checkhealth
```

### View loaded plugins
```vim
:Lazy
```

### Debug keybindings
Press `<Space>` and wait - Which-key will show available bindings.

### Rebuild after changes
```bash
darwin-rebuild switch --flake /etc/nix-darwin
```

---

## File Structure

```
~/.config/neovim/
├── flake.nix      # Main configuration (all NixVim options)
├── flake.lock     # Locked dependencies
└── README.md      # This file
```

---

## Useful Commands

| Command | Description |
|---------|-------------|
| `:LazyGit` | Open Lazygit |
| `:Telescope` | Open Telescope |
| `:Mason` | Not used (Nix manages everything) |
| `:LspInfo` | Show LSP status |
| `:Neotree` | Open file explorer |
| `:Trouble` | Open diagnostics panel |

---

## Updating

```bash
cd ~/.config/neovim
nix flake update
darwin-rebuild switch --flake /etc/nix-darwin
```

This updates NixVim and all plugins to their latest versions.
