#!/bin/bash

set -e

DEST_DIR="$HOME/.config/home-manager"
SOURCE_DIR=${1:-"./home-manager"}

echo "--- Starting Home Manager Setup ---"
echo "Using source directory: $SOURCE_DIR"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory '$SOURCE_DIR' not found."
    echo "Please ensure the path is correct or run this script from the correct location."
    exit 1
fi

echo "Step 1: Checking for destination directory..."
if [ ! -d "$DEST_DIR" ]; then
    echo "-> '$DEST_DIR' not found. Creating it now."
    mkdir -p "$DEST_DIR"
else
    echo "-> '$DEST_DIR' already exists."
fi

echo "Step 2: Moving configuration files from '$SOURCE_DIR' to '$DEST_DIR'..."
cp -a "$SOURCE_DIR/." "$DEST_DIR/"
echo "-> Files moved successfully."

echo "Step 3: Running the Home Manager activation script..."
cd "$DEST_DIR"
sudo USER=$USER HOME=$HOME nix --extra-experimental-features "nix-command flakes" run .#homeConfigurations.tomasmazvila.activation-script

echo "--- Home Manager Setup Complete! ---"

