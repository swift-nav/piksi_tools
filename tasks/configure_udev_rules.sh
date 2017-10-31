#!/bin/bash
current_user=$(who | awk '{print $1}')
echo "Creating new udev rule 99-piksi.rules with the following lines"
sudo tee /etc/udev/rules.d/99-piksi.rules <<EOF
ATTRS{idProduct}=="6014", ATTRS{idVendor}=="0403", MODE="666", GROUP="dialout"
ATTRS{idProduct}=="8398", ATTRS{idVendor}=="0403", MODE="666", GROUP="dialout"
ATTRS{idProduct}=="A4A7", ATTRS{idVendor}=="0525", MODE="666", GROUP="dialout"
EOF
echo "Adding current user to the dialout group."
sudo usermod -a -G dialout $current_user 
echo "reloading udev rules"
sudo udevadm control --reload-rules
