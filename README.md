# Dotfiles

My declarative macOS configuration using Nix.

## What's Included

- **nix-darwin** - macOS system configuration
- **home-manager** - User environment and dotfiles
- **NixVim** - Fully configured Neovim

## Structure

```
dotfiles/
├── flake.nix           # Main flake entry point
├── flake.lock          # Locked dependencies
├── configuration.nix   # nix-darwin system config
├── home.nix            # home-manager user config
└── neovim/
    ├── default.nix     # Neovim configuration
    └── README.md       # Neovim keybindings reference
```

## Prerequisites

1. **Nix** with flakes enabled
2. **nix-darwin** installed

If starting fresh on a new Mac:
```bash
# Install Nix
curl -L https://nixos.org/nix/install | sh

# Enable flakes (add to ~/.config/nix/nix.conf)
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf

# Install nix-darwin
nix run nix-darwin -- switch --flake github:tomazvila/dotfiles
```

## Installation

### From GitHub (recommended)

```bash
darwin-rebuild switch --flake github:tomazvila/dotfiles
```

### From local clone

```bash
git clone https://github.com/tomazvila/dotfiles.git ~/dotfiles
darwin-rebuild switch --flake ~/dotfiles
```

## Daily Usage

### Rebuild after changes

```bash
darwin-rebuild switch --flake ~/dotfiles
```

### Test Neovim standalone

```bash
nix run ~/dotfiles#neovim
```

### Update all dependencies

```bash
cd ~/dotfiles
nix flake update
darwin-rebuild switch --flake .
git add flake.lock
git commit -m "Update flake inputs"
git push
```

### Update specific input

```bash
cd ~/dotfiles
nix flake update nixvim  # or nixpkgs, home-manager, etc.
darwin-rebuild switch --flake .
```

## Making Changes

### Add a system package

Edit `configuration.nix`:
```nix
environment.systemPackages = [
  pkgs.some-package
];
```

### Add a user package

Edit `home.nix`:
```nix
home.packages = [
  pkgs.some-package
];
```

### Add a Neovim plugin

Edit `neovim/default.nix`:
```nix
plugins.some-plugin.enable = true;
```

### Add a new keybinding

Edit `neovim/default.nix` in the `keymaps` section:
```nix
keymaps = [
  { mode = "n"; key = "<leader>xx"; action = "<cmd>SomeCommand<CR>"; options.desc = "Description"; }
];
```

### Add a Homebrew cask

Edit `configuration.nix`:
```nix
homebrew.casks = [
  "some-app"
];
```

## Workflow for Iterating

1. **Make changes** to the relevant `.nix` file
2. **Test locally**:
   ```bash
   darwin-rebuild switch --flake ~/dotfiles
   ```
3. **Commit and push**:
   ```bash
   cd ~/dotfiles
   git add -A
   git commit -m "Description of changes"
   git push
   ```

## Configuration Details

### nix-darwin (`configuration.nix`)

- System-wide packages
- Homebrew casks (e.g., Ghostty terminal)
- Zsh as default shell
- Nix flakes enabled

### home-manager (`home.nix`)

- User packages: git, ripgrep, nodejs, neovim
- Git configuration
- Zsh with completions and custom init

### Neovim (`neovim/default.nix`)

| Category | Details |
|----------|---------|
| **Theme** | Catppuccin Mocha |
| **Leader** | `<Space>` |
| **LSP** | TypeScript, Nix, Python, Scala, Haskell, Rust, Lua, HTML/CSS/JSON, YAML |
| **Plugins** | Treesitter, Telescope, Neo-tree, Lualine, Which-key, Gitsigns, DAP, and more |

See `neovim/README.md` for full keybindings reference.

## Troubleshooting

### Rebuild fails

```bash
# Check what would be built
darwin-rebuild build --flake ~/dotfiles

# Show full trace on error
darwin-rebuild switch --flake ~/dotfiles --show-trace
```

### Neovim issues

```bash
# Run health check
nvim +checkhealth

# Check LSP status
:LspInfo

# Check loaded plugins
:Lazy
```

### Reset to clean state

```bash
# Rebuild from GitHub (ignores local changes)
darwin-rebuild switch --flake github:tomazvila/dotfiles
```

### Rollback to previous generation

```bash
# List generations
darwin-rebuild --list-generations

# Rollback
darwin-rebuild switch --rollback
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `darwin-rebuild switch --flake ~/dotfiles` | Rebuild system |
| `nix flake update` | Update all inputs |
| `nix flake show` | Show flake outputs |
| `nix run ~/dotfiles#neovim` | Run neovim standalone |
| `nvim` | Launch Neovim |
| `darwin-rebuild --list-generations` | List system generations |

## Resources

- [nix-darwin manual](https://daiderd.com/nix-darwin/manual/)
- [home-manager manual](https://nix-community.github.io/home-manager/)
- [NixVim documentation](https://nix-community.github.io/nixvim/)
- [Nix flakes](https://nixos.wiki/wiki/Flakes)
