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
