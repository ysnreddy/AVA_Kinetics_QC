#!/bin/bash

# Script to generate self-signed SSL certificates for webhook listener

CERT_DIR="./certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"

# Create certs directory if it doesn't exist
mkdir -p $CERT_DIR

echo "🔐 Generating self-signed SSL certificate..."

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -nodes \
    -out $CERT_FILE \
    -keyout $KEY_FILE \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=host.docker.internal"

if [ $? -eq 0 ]; then
    echo "✅ Certificates generated successfully:"
    echo "   Certificate: $CERT_FILE"
    echo "   Private Key: $KEY_FILE"
    echo ""
    echo "⚠️  Note: Since this is a self-signed certificate, CVAT might show SSL warnings."
    echo "    You may need to configure CVAT to accept self-signed certificates."
else
    echo "❌ Failed to generate certificates"
    exit 1
fi

# Set appropriate permissions
chmod 644 $CERT_FILE
chmod 600 $KEY_FILE

echo ""
echo "📝 Next steps:"
echo "1. Update CVAT webhook configuration to accept self-signed certificates"
echo "2. Or use HTTP instead: http://host.docker.internal:5001/webhook"