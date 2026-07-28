#!/bin/bash
set -e

# Mac App Code Signing and Notarization Script
# This script signs the compiled PythonLure.app, packages it into a zip, and sends it to Apple for Notarization.

APP_PATH="backend/dist/PythonLure.app"
ENTITLEMENTS="scripts/entitlements.mac.plist"
ZIP_PATH="backend/dist/PythonLure-Mac.zip"
BUNDLE_ID="edu.ufl.ramccleery.pythonlure"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH not found! Please run scripts/build_app.sh first."
    exit 1
fi

if [ -z "$DEVELOPER_ID_CERT_NAME" ] || [ -z "$APPLE_ID" ] || [ -z "$APP_PASSWORD" ] || [ -z "$TEAM_ID" ]; then
    echo "Error: Missing required environment variables."
    echo "Please set DEVELOPER_ID_CERT_NAME, APPLE_ID, APP_PASSWORD, and TEAM_ID."
    echo "Example:"
    echo '  export DEVELOPER_ID_CERT_NAME="Developer ID Application: Your Professor Name (ABC123DEFG)"'
    echo '  export APPLE_ID="professor@ufl.edu"'
    echo '  export APP_PASSWORD="abcd-efgh-ijkl-mnop"'
    echo '  export TEAM_ID="ABC123DEFG"'
    exit 1
fi

echo "==========================================="
echo "1. Code Signing PythonLure.app"
echo "==========================================="
# Remove any existing signature to be safe
codesign --remove-signature "$APP_PATH" 2>/dev/null || true

# PyInstaller creates hundreds of .so and .dylib files. 
# We need to deeply sign everything using the Hardened Runtime.
echo "Deep signing application bundle..."
codesign --deep --force --verify --verbose --timestamp --options runtime --entitlements "$ENTITLEMENTS" --sign "$DEVELOPER_ID_CERT_NAME" "$APP_PATH"

echo "Verifying signature..."
codesign --verify --verbose --strict "$APP_PATH"
spctl -a -t exec -vv "$APP_PATH" || echo "Note: Gatekeeper verification might fail until Notarization is complete."

echo "==========================================="
echo "2. Packaging App into ZIP"
echo "==========================================="
rm -f "$ZIP_PATH"
# Use ditto to preserve symlinks and attributes safely
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "Created $ZIP_PATH"

echo "==========================================="
echo "3. Submitting to Apple Notary Service"
echo "==========================================="
echo "Uploading to Apple (this may take a few minutes)..."
xcrun notarytool submit "$ZIP_PATH" \
    --apple-id "$APPLE_ID" \
    --password "$APP_PASSWORD" \
    --team-id "$TEAM_ID" \
    --wait

echo "==========================================="
echo "4. Stapling Notarization Ticket"
echo "==========================================="
echo "Stapling ticket to app..."
xcrun stapler staple "$APP_PATH"

echo "==========================================="
echo "5. Re-Packaging Stapled App into Final ZIP"
echo "==========================================="
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo "✅ SUCCESS! $ZIP_PATH is now fully signed, notarized, and stapled."
echo "You can now distribute this ZIP file to your field workers."
