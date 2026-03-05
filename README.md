# Govee Local API

[![Upload Python Package](https://github.com/Galorhallen/govee-local-api/actions/workflows/deploy.yml/badge.svg?event=release)](https://github.com/Galorhallen/govee-local-api/actions/workflows/deploy.yml)

Please note that scene and segment support is still **very** experimental.

# Requirements

- Python >= 3.9
- Govee Local API enabled. Refer to https://app-h5.govee.com/user-manual/wlan-guide

# Installation

## Home Assistant (via HACS)

1. Open HACS in your Home Assistant instance.
2. Click on the three dots in the top right corner and select "Custom repositories".
3. Add this repository URL and select "Integration" as the category.
4. Click "Add" and then install the "Govee Local API" integration.
5. Restart Home Assistant.

## Python library

From your terminal, run

    pip install govee-local-api

or

    python3 -m pip install govee-local-api
