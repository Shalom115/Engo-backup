#!/bin/bash
# Double-click to start Engo chat and open it in the browser.
cd "$(dirname "$0")"
open -g "http://127.0.0.1:8765" 2>/dev/null &
(sleep 2 && open "http://127.0.0.1:8765") &
exec python3.12 -m comms.webchat
