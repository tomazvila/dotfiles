{ config, lib, ... }:

{
  # AeroSpace configuration
  # Docs: https://nikitabobko.github.io/AeroSpace/guide
  home.file.".aerospace.toml".text = ''
    # Start AeroSpace at login
    start-at-login = true

    # Normalizations
    enable-normalization-flatten-containers = true
    enable-normalization-opposite-orientation-for-nested-containers = true

    # Mouse follows focus
    on-focused-monitor-changed = ['move-mouse monitor-lazy-center']

    # Gaps
    [gaps]
    inner.horizontal = 10
    inner.vertical = 10
    outer.left = 10
    outer.bottom = 10
    outer.top = 10
    outer.right = 10

    # Main mode bindings
    [mode.main.binding]
    # Focus windows (vim-style)
    alt-h = 'focus left'
    alt-j = 'focus down'
    alt-k = 'focus up'
    alt-l = 'focus right'

    # Move windows
    alt-shift-h = 'move left'
    alt-shift-j = 'move down'
    alt-shift-k = 'move up'
    alt-shift-l = 'move right'

    # Resize windows
    alt-minus = 'resize smart -50'
    alt-equal = 'resize smart +50'

    # Layout controls
    alt-comma = 'layout tiles horizontal vertical'
    alt-period = 'layout accordion horizontal vertical'
    alt-f = 'fullscreen'
    alt-shift-f = 'layout floating tiling'

    # Workspaces (1-9)
    alt-1 = 'workspace 1'
    alt-2 = 'workspace 2'
    alt-3 = 'workspace 3'
    alt-4 = 'workspace 4'
    alt-5 = 'workspace 5'
    alt-6 = 'workspace 6'
    alt-7 = 'workspace 7'
    alt-8 = 'workspace 8'
    alt-9 = 'workspace 9'

    # Move window to workspace
    alt-shift-1 = 'move-node-to-workspace 1'
    alt-shift-2 = 'move-node-to-workspace 2'
    alt-shift-3 = 'move-node-to-workspace 3'
    alt-shift-4 = 'move-node-to-workspace 4'
    alt-shift-5 = 'move-node-to-workspace 5'
    alt-shift-6 = 'move-node-to-workspace 6'
    alt-shift-7 = 'move-node-to-workspace 7'
    alt-shift-8 = 'move-node-to-workspace 8'
    alt-shift-9 = 'move-node-to-workspace 9'

    # Cycle through windows
    alt-tab = 'workspace-back-and-forth'
    alt-shift-tab = 'move-workspace-to-monitor --wrap-around next'

    # Service mode (for less common actions)
    alt-shift-semicolon = 'mode service'

    # Service mode bindings
    [mode.service.binding]
    esc = 'mode main'
    r = ['flatten-workspace-tree', 'mode main']
    f = ['layout floating tiling', 'mode main']
    backspace = ['close-all-windows-but-current', 'mode main']

    # Balance sizes
    alt-shift-equal = ['balance-sizes', 'mode main']

    # Join with adjacent windows
    alt-shift-h = ['join-with left', 'mode main']
    alt-shift-j = ['join-with down', 'mode main']
    alt-shift-k = ['join-with up', 'mode main']
    alt-shift-l = ['join-with right', 'mode main']

    # App-specific rules
    [[on-window-detected]]
    if.app-id = 'com.mitchellh.ghostty'
    run = 'move-node-to-workspace 1'

    [[on-window-detected]]
    if.app-id = 'com.apple.Safari'
    run = 'move-node-to-workspace 2'

    [[on-window-detected]]
    if.app-id = 'com.apple.systempreferences'
    run = 'layout floating'

    [[on-window-detected]]
    if.app-id = 'com.apple.calculator'
    run = 'layout floating'

    [[on-window-detected]]
    if.app-id = 'com.apple.finder'
    if.window-title-regex-substring = 'Copy|Move|Delete|Eject'
    run = 'layout floating'
  '';
}
