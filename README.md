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

