# Dotfiles

Goal of this respository is to replicate easily and smoothly the setup of workstation in another machine. Have whole setup (tools, packages, libraries, dev environments, editor, configuration files...) in another machine in couple of minutes.

## User

Create user:

```
sudo useradd -m username
```

Set user password:
```
sudo passwd username
```

Add user to superusers group:
```
sudo usermode -aG sudo username
```

## Ssh

Generate ssh key:
```
ssh-keygen -t rsa
```

Copy key to remote server:
```
ssh-copy-id remote_user@remote_IP
```

## Ansible

### Provide inventory file

```
ansible -i inventory.yaml -m ping demo_server_local
```

### Input password to use sudo priveliges

```
ansible-playbook myplaybook.yaml --ask-become-pass
```

or

```
ansible-playbook myplaybook.yaml -K
```

#### Other stuff

 - `--become`, `-b` – This allows you to run the task as a root user without prompting for a password.
 - `--become-user=BECOME_USER` – It allows you to run tasks as another user.

### Run simple bash command with ansible

```
ansible -a "df -Th" all
```

### Managing users

Just use user module. TODO implement playbook to create one user to rule them all.

### Install zsh example

```
ansible-playbook -i ansible/inventory.yaml -l demo_server_remote ansible/playbooks/install-zsh.yaml -K
```

### Pass variable to playbook

```
ansible-playbook -i ansible/inventory.yaml -l demo_server_local ansible/playbooks/set-shell.yaml -e "user=username shell=/bin/bash" -K
```

## Testing with vagrant

Create this file:

```
Vagrant.configure("2") do |config|
    config.vm.box = "alvistack/ubuntu-22.04"
end
```

Run this command:

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

Finaly spin up vm with:
```bash
vagrant up
```

Test ansible scripts with command like:
```bash
ansible-playbook -i ansible/inventory.yaml -l vagrant ansible/playbooks/create-user.yaml -K
```

To get clean state again destroy vm with:
```bash
vagrant destroy
```

## EndGame

1. [ ] Setup user on target machine
2. [ ] Install docker
3. [ ] Install nix and its derivatives
4. [ ] Install nix home-manager and use it to install and setup
    - [ ] neovim
    - [ ] tmux
    - [ ] glew
    - [ ] ripgrep
    - [ ] git
