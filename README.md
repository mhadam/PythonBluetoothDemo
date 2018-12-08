# PythonBluetoothDemo
A /very/ ugly hackathon project to demonstrate accessing the Cocoa API in Python and polling for Bluetooth devices.

A word of advice for any poor soul that decides to work with IOBluetooth (this is scarcely documented and wasn't obvious to me): IOBluetooth requires an active run loop to give asynchronous callbacks. Otherwise you won't get the results!

How to run:
```shell
pip -r requirements.txt
python3 demo.py
```

The project was developed with Python3.7, it'll require a Mac too.
