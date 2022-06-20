# Dotfiles

Goal of this respository is to replicate easily and smoothly the setup of workstation in another machine. Have whole setup (tools, packages, libraries, dev environments, editor, configuration files...) in another machine in couple of minutes.

## User

Create user: To create user use `create-user.yaml` playbook with this command:

```bash
ansible-playbook -i ansible/inventory.yaml -l targetmachine ansible/playbooks/create-user.yaml -K
```

Ssh to target machine

Set user password:

```bash
sudo passwd user
```

## Install docker

Use `install-docker.yaml` playbook like so:

```bash
ansible-playbook -i ansible/inventory.yaml -l targetmachine ansible/playbooks/install-docker.yaml -K
```

## Install Nix

TODO:

ansible role to install nix

### Install manually

This

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

Then

```bash
nix-channel --add https://github.com/nix-community/home-manager/archive/master.tar.gz home-manager
nix-channel --update
nix-channel --add https://github.com/nix-community/home-manager/archive/release-22.05.tar.gz home-manager
nix-channel --update
```

Add this to shell:

```bash
export NIX_PATH=$HOME/.nix-defexpr/channels:/nix/var/nix/profiles/per-user/root/channels${NIX_PATH:+:$NIX_PATH}
```

Install **home-manager**:

```bash
nix-shell '<home-manager>' -A install
```

Source current shell:

```bash
. "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
```

> **_NOTE:_**  Somewhy installation doesn't work with custom created user

## home-manager

## Ansible

### Provide inventory file

```bash
ansible -i inventory.yaml -m ping demo_server_local
```

### Input password to use sudo priveliges

```bash
ansible-playbook myplaybook.yaml --ask-become-pass
```

or

```bash
ansible-playbook myplaybook.yaml -K
```

#### Other stuff

- `--become`, `-b` – This allows you to run the task as a root user without prompting for a password.
- `--become-user=BECOME_USER` – It allows you to run tasks as another user.

### Run simple bash command with ansible

```bash
ansible -a "df -Th" all
```

### Install zsh example

```bash
ansible-playbook -i ansible/inventory.yaml -l demo_server_remote ansible/playbooks/install-zsh.yaml -K
```

### Pass variable to playbook

```bash
ansible-playbook -i ansible/inventory.yaml -l demo_server_local ansible/playbooks/set-shell.yaml -e "user=username shell=/bin/bash" -K
```

## Testing with vagrant

Create this file if it doesn't exist already in new directory:

```bash
Vagrant.configure("2") do |config|
    config.vm.box = "alvistack/ubuntu-22.04"
end
```

Run this command from the same directory where the vagrant file was created:

```bash
vagrant init
```

If ssh key doesn't exist issue this command:

```bash
ssh-keygen -t rsa
```

If ssh-key was added issue this command:

```bash
ssh-keygen -f "/home/user/.ssh/known_hosts" -R "[127.0.0.1]:2222"
```

Spin up vm with:

```bash
vagrant up
```

Then issue this command:

```bash
ssh-copy-id -p 2222 vagrant@127.0.0.1
```

Add this to `~/.ssh/config`:

```
Host vagrant
        HostName 127.0.0.1
        User vagrant
        Port 2222
```

Now you can ssh to vm with just: `ssh vagrant`

Test ansible scripts with command like:

```bash
ansible-playbook -i ansible/inventory/inventory.yaml -l vagrant ansible/playbooks/create-user.yaml -K
```

To get clean state again destroy vm with:

```bash
vagrant destroy
```

## EndGame

1. [x] Setup user on target machine
2. [x] Install docker
3. [ ] Install nix and its derivatives
4. [ ] Install nix home-manager and use it to install and setup
    - [ ] neovim
    - [ ] tmux
    - [ ] glew
    - [ ] ripgrep
    - [ ] git
