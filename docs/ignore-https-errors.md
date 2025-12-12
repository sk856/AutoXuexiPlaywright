# Ignore HTTPS Errors Configuration

## Overview

The `ignore_https_errors` configuration option allows the browser to bypass SSL/TLS certificate verification errors. This is useful in environments where network-level traffic modification tools (such as ua3f on OpenWrt routers) may interfere with HTTPS connections.

## Use Case

When running AutoXuexiPlaywright on OpenWrt routers with the ua3f plugin enabled, you may encounter network connectivity issues on port 443 (HTTPS). This is because ua3f modifies network traffic, which can cause SSL certificate verification to fail. Enabling the `ignore_https_errors` option allows the browser to bypass these verification errors.

## Configuration

### GUI Mode

In the GUI settings window, check the "Ignore HTTPS Errors" checkbox to enable this option.

### Configuration File

Add the following to your `config.json`:

```json
{
  "ignore_https_errors": true
}
```

### Default Value

By default, `ignore_https_errors` is set to `false` for security reasons. Only enable it when necessary.

## Security Considerations

**Warning**: Enabling this option bypasses SSL/TLS certificate verification, which reduces security. Only use this option in trusted networks or when absolutely necessary.

When `ignore_https_errors` is enabled:
- The browser will accept invalid or self-signed SSL certificates
- Man-in-the-middle attacks become possible
- Secure HTTPS connections are less secure

## When to Enable

Enable `ignore_https_errors` when:
- Running on OpenWrt with ua3f or similar network modification tools
- Using a transparent proxy that intercepts HTTPS traffic
- Encountering SSL certificate errors that prevent normal operation

## When NOT to Enable

Do NOT enable `ignore_https_errors` when:
- Running in a production environment
- Processing sensitive data
- Not experiencing SSL-related connection issues
- Security is a primary concern
