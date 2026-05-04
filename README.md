[![willo](https://img.shields.io/github/release/38decibel/willo/all.svg?style=plastic&label=Current%20release)](https://github.com/38decibel/willo) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=plastic)](https://github.com/hacs/integration) [![downloads](https://img.shields.io/github/downloads/38decibel/willo/total?style=plastic&label=Total%20downloads)](https://github.com/38decibel/willo)

# Willo — Home Assistant Integration

Home Assistant custom integration for the **[Wiliv Willo](https://www.wiliv.com/products/willo-borne-anti-moustique)** mosquito trap.

> ⚠️ This integration is not affiliated with or endorsed by Wiliv / INYO (ex. Ma Boite A Moustique).

## About the Willo

The **Willo** (ref. M-BOX CO2) is a premium outdoor mosquito trap by [Wiliv](https://www.wiliv.com), based on the **Ma Boite A Moustique** system.

The official **Wiliv mobile app** allows scheduling CO₂ diffusion hours and managing the LED light. This integration brings the same control natively into Home Assistant.


## Features

- 💡 **LED switch** — turn the interior UV light on/off
- 🕐 **24-hour schedule** — enable/disable CO₂ diffusion for each hour of the day
- 📡 **Firmware sensor** — display device firmware version (diagnostic)
- 🕰️ **Auto clock sync** — device date & time are synchronized with Home Assistant on each connection


## Requirements

- Home Assistant 2024.1 or later
- Bluetooth adapter accessible by Home Assistant
- Willo device powered on and in Bluetooth range (advertised as `MBAM UART Service`)

## Installation

### Via HACS (recommended)

1. In HACS, go to **Integrations** → **Custom repositories**
2. Add `https://github.com/38decibel/willo` with category **Integration**
3. Install **Willo**
4. Restart Home Assistant

### Manual

1. Copy `custom_components/willo/` into your HA `config/custom_components/` folder
2. Restart Home Assistant


## Configuration
### Automatic discovery (recommended)

When your Willo device is powered on and within Bluetooth range, Home Assistant will detect it automatically and display a notification in **Settings → Devices & Services**:

1. Click **Configure** on the discovered Willo notification
2. Confirm the device name and (optionally) set a friendly name
3. Optional: add the Entity ID of a HA Schedule Helper (e.g. `schedule.willo_schedule`). Leave blank to use the 4 time slot entities instead.

> 💡 Automatic discovery relies on the device advertising itself as `MBAM*` over Bluetooth LE. Make sure your Willo is powered on before adding the integration.

### Manual setup

If automatic discovery does not trigger (e.g. device not yet in range):

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **WILLO**
3. If no device is detected nearby, the form will fall back to manual entry
4. Enter your device MAC address (e.g. `B0:B2:1C:xx:yy:zz`) and a friendly name
5. Optional: add the Entity ID of a HA Schedule Helper. Leave blank to use the 4 time slot entities instead.

> 💡 If devices are detected nearby, a list of `MBAM*` devices will be proposed. You can also choose **"Enter manually"** from the list to type the MAC address directly.

## BLE Protocol

This integration was reverse-engineered using a **Nordic nRF Sniffer** and **Wireshark**.  
The Willo device exposes a standard **Nordic UART Service (NUS)**:

| Characteristic | UUID |
|----------------|------|
| TX (write) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| RX (notify) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |

### Command reference

| Command | Description |
|---------|-------------|
| `#I!1*` | LED ON |
| `#I!0*` | LED OFF |
| `#H?` | Read CO₂ diffusion schedule |
| `#H!<24bits>*` | Write CO₂ diffusion schedule |
| `#V?` | Read firmware version |
| `#D!YYMMDD*` | Set device date |
| `#T!HHMMSS*` | Set device time |

### Schedule format

A 24-character string of `0` and `1`, one bit per hour (index 0 = midnight, index 23 = 11pm).

**Example:**
```
000000011000000011111100
```
→ CO₂ active at **7h, 8h** and **16h → 21h**

## Disclaimer

This is an unofficial integration developed by reverse-engineering the Bluetooth protocol.  
Use at your own risk. Not affiliated with Wiliv or INYO (ex. Ma Boite A Moustique).

## License

MIT
