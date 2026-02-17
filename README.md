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

- User packages: git, ripgrep, bat, difftastic, jq, hyperfine, procs, nodejs, neovim
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

## CLI Tools

Modern replacements for traditional Unix utilities, installed via `home.nix`.

### bat — A better `cat`

Syntax-highlighted file viewer with line numbers, git integration, and automatic paging.

**When to use:** Anytime you'd use `cat` or `less` to read files. Especially useful for code files.

```bash
bat file.py                    # View file with syntax highlighting
bat --diff file.py             # Show git changes inline
bat -l json data.txt           # Force a specific syntax (json)
bat -p file.py                 # Plain output (no line numbers/header), useful for piping
bat src/*.rs                   # View multiple files
```

### ripgrep (`rg`) — A better `grep`

Extremely fast recursive text search. Respects `.gitignore`, skips binary files automatically.

**When to use:** Searching for text across a codebase. Replaces `grep -r`.

```bash
rg "TODO"                      # Search current directory recursively
rg "fn main" --type rust       # Search only Rust files
rg "error" --glob "*.log"      # Search only log files
rg "pattern" -C 3              # Show 3 lines of context around matches
rg "class \w+" -o              # Show only the matching part
rg "old_name" --files-with-matches  # List files containing matches
```

### difftastic (`difft`) — Structural diffs

A syntax-aware diff tool. Understands code structure so it shows meaningful changes instead of line-by-line noise.

**When to use:** Reviewing code changes, especially refactors where code moved around. Use as a git difftool.

```bash
difft file_old.py file_new.py  # Compare two files
difft dir_a/ dir_b/            # Compare two directories

# Use as git diff tool (one-off)
GIT_EXTERNAL_DIFF=difft git diff

# Or configure permanently
git config --global diff.external difft
```

### jq — JSON processor

Command-line JSON parser, filter, and transformer.

**When to use:** Working with JSON from APIs, config files, or log output. Anytime you need to extract, filter, or reshape JSON data.

```bash
cat data.json | jq '.'                  # Pretty-print JSON
curl -s api/endpoint | jq '.name'       # Extract a field
jq '.users[] | .email' data.json        # Extract nested array field
jq '.items | length' data.json          # Count array items
jq 'select(.age > 30)' data.json        # Filter objects
jq '{name, email}' data.json            # Pick specific fields
jq -r '.url' data.json                  # Raw output (no quotes)
```

### hyperfine — CLI benchmarking

Statistical benchmarking for shell commands. Runs multiple iterations with warmup and reports mean, min, max, and standard deviation.

**When to use:** Comparing performance of commands, scripts, or different implementations. Replaces unreliable single-run `time` measurements.

```bash
hyperfine 'sleep 0.3'                           # Benchmark a single command
hyperfine 'rg pattern' 'grep -r pattern'         # Compare two commands
hyperfine --warmup 3 'my-program'                # Run 3 warmup iterations first
hyperfine --min-runs 20 'my-script.sh'           # Run at least 20 iterations
hyperfine -p 'make clean' 'make build'           # Run preparation command before each
hyperfine --export-markdown bench.md 'cmd'       # Export results as markdown table
```

### procs — A better `ps`

Modern process viewer with color output, keyword search, tree view, and human-readable formatting.

**When to use:** Finding and inspecting running processes. Replaces `ps aux | grep`.

```bash
procs                          # Show all processes (colored, formatted)
procs node                     # Search for processes by keyword
procs --tree                   # Show process tree
procs --sortd cpu              # Sort by CPU usage (descending)
procs --sortd mem              # Sort by memory usage (descending)
procs -w 5                     # Watch mode, refresh every 5 seconds
```

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
