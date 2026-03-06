# Neovim configuration module for NixVim
{ nixpkgs, system }:
{
  # ============================================
  # GENERAL SETTINGS
  # ============================================
  globals = {
    mapleader = " ";
    maplocalleader = " ";
  };

  # Fix treesitter trying to write to nix store
  extraConfigLuaPre = ''
    -- Set parser install dir to writable location (prevents nix store write errors)
    vim.opt.runtimepath:prepend(vim.fn.stdpath("data") .. "/site")
  '';

  opts = {
    number = true;
    relativenumber = true;
    shiftwidth = 2;
    tabstop = 2;
    softtabstop = 2;
    expandtab = true;
    smartindent = true;
    wrap = true;
    linebreak = true;
    swapfile = false;
    backup = false;
    undofile = true;
    hlsearch = false;
    incsearch = true;
    termguicolors = true;
    scrolloff = 8;
    signcolumn = "yes";
    updatetime = 50;
    colorcolumn = "100";
    mouse = "a";
    clipboard = "unnamedplus";
    splitright = true;
    splitbelow = true;
    ignorecase = true;
    smartcase = true;
    cursorline = true;
  };

  # ============================================
  # COLORSCHEME
  # ============================================
  colorschemes.catppuccin = {
    enable = true;
    settings = {
      flavour = "mocha";
      integrations = {
        cmp = true;
        gitsigns = true;
        neotree = true;
        treesitter = true;
        notify = true;
        which_key = true;
        fidget = true;
        native_lsp = {
          enabled = true;
          underlines = {
            errors = [ "undercurl" ];
            hints = [ "undercurl" ];
            warnings = [ "undercurl" ];
            information = [ "undercurl" ];
          };
        };
      };
    };
  };

  # ============================================
  # KEYMAPS
  # ============================================
  keymaps = [
    # General
    { mode = "n"; key = "<Esc>"; action = "<cmd>nohlsearch<CR>"; options.desc = "Clear search highlight"; }
    { mode = "n"; key = "<leader>w"; action = "<cmd>w<CR>"; options.desc = "Save file"; }
    { mode = "n"; key = "<leader>q"; action = "<cmd>q<CR>"; options.desc = "Quit"; }
    { mode = "n"; key = "<leader>x"; action = "<cmd>x<CR>"; options.desc = "Save and quit"; }

    # Window navigation
    { mode = "n"; key = "<C-h>"; action = "<C-w>h"; options.desc = "Move to left window"; }
    { mode = "n"; key = "<C-j>"; action = "<C-w>j"; options.desc = "Move to lower window"; }
    { mode = "n"; key = "<C-k>"; action = "<C-w>k"; options.desc = "Move to upper window"; }
    { mode = "n"; key = "<C-l>"; action = "<C-w>l"; options.desc = "Move to right window"; }

    # Window splits
    { mode = "n"; key = "<leader>sv"; action = "<cmd>vsplit<CR>"; options.desc = "Split vertical"; }
    { mode = "n"; key = "<leader>sh"; action = "<cmd>split<CR>"; options.desc = "Split horizontal"; }
    { mode = "n"; key = "<leader>se"; action = "<C-w>="; options.desc = "Equal split sizes"; }
    { mode = "n"; key = "<leader>sx"; action = "<cmd>close<CR>"; options.desc = "Close split"; }

    # Buffer navigation
    { mode = "n"; key = "<S-h>"; action = "<cmd>bprevious<CR>"; options.desc = "Previous buffer"; }
    { mode = "n"; key = "<S-l>"; action = "<cmd>bnext<CR>"; options.desc = "Next buffer"; }
    { mode = "n"; key = "<leader>bd"; action = "<cmd>bdelete<CR>"; options.desc = "Delete buffer"; }

    # Move lines
    { mode = "v"; key = "J"; action = ":m '>+1<CR>gv=gv"; options.desc = "Move line down"; }
    { mode = "v"; key = "K"; action = ":m '<-2<CR>gv=gv"; options.desc = "Move line up"; }

    # Stay centered
    { mode = "n"; key = "<C-d>"; action = "<C-d>zz"; options.desc = "Scroll down centered"; }
    { mode = "n"; key = "<C-u>"; action = "<C-u>zz"; options.desc = "Scroll up centered"; }
    { mode = "n"; key = "n"; action = "nzzzv"; options.desc = "Next search centered"; }
    { mode = "n"; key = "N"; action = "Nzzzv"; options.desc = "Prev search centered"; }

    # Better paste
    { mode = "x"; key = "<leader>p"; action = ''"_dP''; options.desc = "Paste without yanking"; }

    # Copy to system clipboard
    { mode = [ "n" "v" ]; key = "<leader>y"; action = ''"+y''; options.desc = "Yank to clipboard"; }
    { mode = "n"; key = "<leader>Y"; action = ''"+Y''; options.desc = "Yank line to clipboard"; }

    # Delete without yanking
    { mode = [ "n" "v" ]; key = "<leader>d"; action = ''"_d''; options.desc = "Delete without yank"; }

    # Telescope
    { mode = "n"; key = "<leader>ff"; action = "<cmd>Telescope find_files<CR>"; options.desc = "Find files"; }
    { mode = "n"; key = "<leader>fg"; action = "<cmd>Telescope live_grep<CR>"; options.desc = "Live grep"; }
    { mode = "n"; key = "<leader>fb"; action = "<cmd>Telescope buffers<CR>"; options.desc = "Find buffers"; }
    { mode = "n"; key = "<leader>fh"; action = "<cmd>Telescope help_tags<CR>"; options.desc = "Help tags"; }
    { mode = "n"; key = "<leader>fo"; action = "<cmd>Telescope oldfiles<CR>"; options.desc = "Recent files"; }
    { mode = "n"; key = "<leader>fw"; action = "<cmd>Telescope grep_string<CR>"; options.desc = "Grep word under cursor"; }
    { mode = "n"; key = "<leader>fd"; action = "<cmd>Telescope diagnostics<CR>"; options.desc = "Diagnostics"; }
    { mode = "n"; key = "<leader>fs"; action = "<cmd>Telescope lsp_document_symbols<CR>"; options.desc = "Document symbols"; }
    { mode = "n"; key = "<leader>fr"; action = "<cmd>Telescope resume<CR>"; options.desc = "Resume last search"; }
    { mode = "n"; key = "<leader>gc"; action = "<cmd>Telescope git_commits<CR>"; options.desc = "Git commits"; }
    { mode = "n"; key = "<leader>gb"; action = "<cmd>Telescope git_branches<CR>"; options.desc = "Git branches"; }
    { mode = "n"; key = "<leader>gs"; action = "<cmd>Telescope git_status<CR>"; options.desc = "Git status"; }

    # Neo-tree
    { mode = "n"; key = "<leader>e"; action = "<cmd>Neotree toggle<CR>"; options.desc = "Toggle file explorer"; }
    { mode = "n"; key = "<leader>o"; action = "<cmd>Neotree focus<CR>"; options.desc = "Focus file explorer"; }

    # LSP
    { mode = "n"; key = "gd"; action = "<cmd>lua vim.lsp.buf.definition()<CR>"; options.desc = "Go to definition"; }
    { mode = "n"; key = "gD"; action = "<cmd>lua vim.lsp.buf.declaration()<CR>"; options.desc = "Go to declaration"; }
    { mode = "n"; key = "gi"; action = "<cmd>lua vim.lsp.buf.implementation()<CR>"; options.desc = "Go to implementation"; }
    { mode = "n"; key = "gr"; action = "<cmd>Telescope lsp_references<CR>"; options.desc = "Find references"; }
    { mode = "n"; key = "K"; action = "<cmd>lua vim.lsp.buf.hover()<CR>"; options.desc = "Hover documentation"; }
    { mode = "n"; key = "<leader>ca"; action = "<cmd>lua vim.lsp.buf.code_action()<CR>"; options.desc = "Code actions"; }
    { mode = "n"; key = "<leader>rn"; action = "<cmd>lua vim.lsp.buf.rename()<CR>"; options.desc = "Rename symbol"; }
    { mode = "n"; key = "<leader>D"; action = "<cmd>lua vim.lsp.buf.type_definition()<CR>"; options.desc = "Type definition"; }
    { mode = "n"; key = "<leader>ds"; action = "<cmd>lua vim.diagnostic.open_float()<CR>"; options.desc = "Show diagnostics"; }
    { mode = "n"; key = "[d"; action = "<cmd>lua vim.diagnostic.goto_prev()<CR>"; options.desc = "Previous diagnostic"; }
    { mode = "n"; key = "]d"; action = "<cmd>lua vim.diagnostic.goto_next()<CR>"; options.desc = "Next diagnostic"; }
    { mode = "n"; key = "<leader>cf"; action = "<cmd>lua vim.lsp.buf.format({ async = true })<CR>"; options.desc = "Format code"; }

    # DAP (Debugger)
    { mode = "n"; key = "<leader>dc"; action = "<cmd>lua require('dap').continue()<CR>"; options.desc = "Debug continue"; }
    { mode = "n"; key = "<leader>do"; action = "<cmd>lua require('dap').step_over()<CR>"; options.desc = "Debug step over"; }
    { mode = "n"; key = "<leader>di"; action = "<cmd>lua require('dap').step_into()<CR>"; options.desc = "Debug step into"; }
    { mode = "n"; key = "<leader>du"; action = "<cmd>lua require('dap').step_out()<CR>"; options.desc = "Debug step out"; }
    { mode = "n"; key = "<leader>db"; action = "<cmd>lua require('dap').toggle_breakpoint()<CR>"; options.desc = "Toggle breakpoint"; }
    { mode = "n"; key = "<leader>dB"; action = "<cmd>lua require('dap').set_breakpoint(vim.fn.input('Breakpoint condition: '))<CR>"; options.desc = "Conditional breakpoint"; }
    { mode = "n"; key = "<leader>dr"; action = "<cmd>lua require('dap').repl.open()<CR>"; options.desc = "Open REPL"; }
    { mode = "n"; key = "<leader>dl"; action = "<cmd>lua require('dap').run_last()<CR>"; options.desc = "Run last"; }
    { mode = "n"; key = "<leader>dt"; action = "<cmd>lua require('dapui').toggle()<CR>"; options.desc = "Toggle DAP UI"; }

    # Trouble (diagnostics list)
    { mode = "n"; key = "<leader>xx"; action = "<cmd>Trouble diagnostics toggle<CR>"; options.desc = "Diagnostics (Trouble)"; }
    { mode = "n"; key = "<leader>xX"; action = "<cmd>Trouble diagnostics toggle filter.buf=0<CR>"; options.desc = "Buffer diagnostics"; }
    { mode = "n"; key = "<leader>cs"; action = "<cmd>Trouble symbols toggle focus=false<CR>"; options.desc = "Symbols (Trouble)"; }
    { mode = "n"; key = "<leader>xL"; action = "<cmd>Trouble loclist toggle<CR>"; options.desc = "Location list"; }
    { mode = "n"; key = "<leader>xQ"; action = "<cmd>Trouble qflist toggle<CR>"; options.desc = "Quickfix list"; }
  ];

  # ============================================
  # PLUGINS
  # ============================================

  # Treesitter - Syntax highlighting
  plugins.treesitter = {
    enable = true;
    nixGrammars = true;
    settings = {
      highlight.enable = true;
      indent.enable = true;
      auto_install = false;
      sync_install = false;
      parser_install_dir.__raw = "vim.fn.stdpath('data') .. '/treesitter'";
    };
    grammarPackages = with nixpkgs.legacyPackages.${system}.vimPlugins.nvim-treesitter.builtGrammars; [
      lua vim vimdoc query
      javascript typescript tsx html css json
      nix
      python
      scala
      haskell
      rust
      go gomod gosum
      markdown markdown_inline
      yaml toml
      bash
      gitignore gitcommit
    ];
  };

  # LSP - Language servers
  plugins.lsp = {
    enable = true;
    servers = {
      ts_ls.enable = true;
      eslint.enable = true;
      nixd.enable = true;
      pyright.enable = true;
      metals.enable = true;
      hls = {
        enable = true;
        installGhc = true;
      };
      rust_analyzer = {
        enable = true;
        installCargo = true;
        installRustc = true;
      };
      lua_ls.enable = true;
      html.enable = true;
      cssls.enable = true;
      jsonls.enable = true;
      yamlls.enable = true;
      gopls.enable = true;
    };
  };

  # Completion
  plugins.cmp = {
    enable = true;
    autoEnableSources = true;
    settings = {
      sources = [
        { name = "nvim_lsp"; }
        { name = "path"; }
        { name = "buffer"; }
        { name = "luasnip"; }
      ];
      mapping = {
        "<C-Space>" = "cmp.mapping.complete()";
        "<C-e>" = "cmp.mapping.close()";
        "<CR>" = "cmp.mapping.confirm({ select = true })";
        "<Tab>" = "cmp.mapping(cmp.mapping.select_next_item(), {'i', 's'})";
        "<S-Tab>" = "cmp.mapping(cmp.mapping.select_prev_item(), {'i', 's'})";
        "<C-n>" = "cmp.mapping.select_next_item()";
        "<C-p>" = "cmp.mapping.select_prev_item()";
        "<C-d>" = "cmp.mapping.scroll_docs(-4)";
        "<C-f>" = "cmp.mapping.scroll_docs(4)";
      };
      snippet.expand = "function(args) require('luasnip').lsp_expand(args.body) end";
    };
  };

  # Snippets
  plugins.luasnip.enable = true;
  plugins.friendly-snippets.enable = true;

  # Telescope - Fuzzy finder
  plugins.telescope = {
    enable = true;
    settings.defaults.file_ignore_patterns = [
      # JavaScript / TypeScript
      "node_modules/"
      "%.next/"
      "dist/"
      # Haskell
      "dist%-newstyle/"
      "%.stack%-work/"
      "%.cabal%-sandbox/"
      # Scala
      "%.metals/"
      "%.bloop/"
      "%.bsp/"
      "target/"
      # Rust
      "target/debug/"
      "target/release/"
      # Python
      "__pycache__/"
      "%.venv/"
      "%.mypy_cache/"
      "%.pytest_cache/"
      # Go
      "vendor/"
      # General
      "%.git/"
      "build/"
      "result/"
    ];
    extensions = {
      fzf-native.enable = true;
      ui-select.enable = true;
    };
  };

  # Neo-tree - File explorer
  plugins.neo-tree = {
    enable = true;
    settings = {
      close_if_last_window = true;
      window = {
        width = 35;
        mappings = {
          "<space>" = "none";
        };
      };
      filesystem = {
        follow_current_file = {
          enabled = true;
        };
        filtered_items = {
          visible = true;
          hide_dotfiles = false;
          hide_gitignored = false;
        };
      };
    };
  };

  # Lualine - Status line
  plugins.lualine = {
    enable = true;
    settings = {
      options = {
        theme = "catppuccin";
        globalstatus = true;
        component_separators = { left = "|"; right = "|"; };
        section_separators = { left = ""; right = ""; };
      };
      sections = {
        lualine_a = [ "mode" ];
        lualine_b = [ "branch" "diff" "diagnostics" ];
        lualine_c = [ "filename" ];
        lualine_x = [ "encoding" "fileformat" "filetype" ];
        lualine_y = [ "progress" ];
        lualine_z = [ "location" ];
      };
    };
  };

  # Which-key - Keybinding hints
  plugins.which-key = {
    enable = true;
    settings = {
      spec = [
        { __unkeyed-1 = "<leader>f"; group = "Find"; }
        { __unkeyed-1 = "<leader>g"; group = "Git"; }
        { __unkeyed-1 = "<leader>c"; group = "Code"; }
        { __unkeyed-1 = "<leader>d"; group = "Debug/Delete"; }
        { __unkeyed-1 = "<leader>s"; group = "Split"; }
        { __unkeyed-1 = "<leader>b"; group = "Buffer"; }
        { __unkeyed-1 = "<leader>x"; group = "Trouble"; }
      ];
    };
  };

  # Gitsigns - Git integration
  plugins.gitsigns = {
    enable = true;
    settings = {
      signs = {
        add = { text = "+"; };
        change = { text = "~"; };
        delete = { text = "_"; };
        topdelete = { text = ""; };
        changedelete = { text = "~"; };
      };
    };
  };

  # Other plugins
  plugins.nvim-autopairs.enable = true;
  plugins.comment.enable = true;
  plugins.fidget.enable = true;
  plugins.trouble.enable = true;
  plugins.todo-comments.enable = true;
  plugins.indent-blankline.enable = true;
  plugins.nvim-surround.enable = true;
  plugins.flash.enable = true;
  plugins.notify.enable = true;
  plugins.dap.enable = true;
  plugins.dap-ui.enable = true;
  plugins.dap-virtual-text.enable = true;
  plugins.dap-python.enable = true;
  plugins.dap-go.enable = true;
  plugins.nix.enable = true;
  plugins.web-devicons.enable = true;
  plugins.lazygit.enable = true;
  plugins.illuminate.enable = true;
}
