# Fork Description

This repository is a fork of [`porkbun-ddns`](https://github.com/mietzen/porkbun-ddns) by **mietzen**, an unofficial DDNS client for Porkbun domains.

## Changes in This Fork

- **Docker Secrets Support:** Allows secure injection of API keys via `_FILE` environment variables.
- **Improved Configuration Handling:** Uses `get_secret_from_env()` to read API keys from either standard environment variables or secret files.
- **Updated Documentation:** Includes examples for using Docker Secrets with `docker-compose` and `docker run`.

---

# Disclaimer

**This package is not related to or developed by Porkbun. No relationship exists between the developer of this package and Porkbun.**

**All trademarks, logos, and brand names are the property of their respective owners. All company, product, and service names used in this package are for identification purposes only. The use of these names, trademarks, and brands does not imply endorsement.**

---

# Porkbun DDNS

`porkbun-ddns` is an unofficial DDNS client for Porkbun domains. This library updates records only when the IP address(es) have changed or the DNS entry did not previously exist. It supports updating both A (IPv4) and AAAA (IPv6) records.

Since [porkbun-dynamic-dns-python](https://github.com/porkbundomains/porkbun-dynamic-dns-python) is deprecated, **mietzen** created this DDNS client as a replacement. Inspired by [con-f-use](https://github.com/con-f-use)'s [pull request](https://github.com/porkbundomains/porkbun-dynamic-dns-python/pull/6), **mietzen** built a `pip` package and a Docker container.

As an alternative to **cert-bun**, you can use **mietzen's** [lego-certbot](https://github.com/mietzen/lego-certbot) image.

---

## Setup on Porkbun

Ensure that any domain you use with this client has **API access enabled**. Refer to the image below:

![API Access Enabled](API_Access_Enabled.png)

If API access is not enabled, you will receive an error indicating that your API keys are invalid, even if they are correct.

---

# Building the Docker Container

To build the Docker container manually, follow these steps:

### 1. Clone the Repository

```sh
git clone https://github.com/noadc_dev/porkbun-ddns.git
cd porkbun-ddns
```

### 2. Build the Docker Image

Run the following command to build the Docker image from the provided `Dockerfile`:

```sh
docker build -t porkbun-ddns:latest -f Docker/Dockerfile .
```

### 3. Verify the Build

After building, check that the image exists by running:

```sh
docker images | grep porkbun-ddns
```

Expected output:

```
porkbun-ddns   latest   <IMAGE_ID>   <TIME_AGO>   <SIZE>
```

---

# Using Docker Secrets

Instead of passing API keys as environment variables, you can use **Docker Secrets** to securely store them.

### 1. Create the Secret Files

Save your API keys to a secure location:

```sh
echo "your-api-key" > /path/to/secrets/PORKBUN_API_KEY
echo "your-secret-api-key" > /path/to/secrets/PORKBUN_SECRET_API_KEY
```

Ensure the files have the correct permissions:

```sh
chmod 600 /path/to/secrets/PORKBUN_API_KEY /path/to/secrets/PORKBUN_SECRET_API_KEY
```

### 2. Configure Your Deployment

When running the container, bind-mount these secrets into `/run/secrets/` inside the container.

#### Difference Between `docker run` and `docker-compose`

- **With `docker run`**, you manually specify the `--mount` option to bind secrets from the host system.
- **With `docker-compose`**, you define `secrets:` in the YAML file, making it more structured and easier to maintain in larger deployments.

---

# Creating the Container

## Docker Compose

```yaml
services:
  porkbun-ddns:
    image: "mietzen/porkbun-ddns:latest"
    container_name: porkbun-ddns
    environment:
      DOMAIN: "domain.com" # Your Porkbun domain
      SUBDOMAINS: "my_subdomain,my_other_subdomain,my_subsubdomain.my_subdomain" # Subdomains separated by commas. Can be left empty.
      SECRETAPIKEY: "<YOUR-SECRETAPIKEY>" # Pass your Porkbun Secret API Key in plaintext
      APIKEY: "<YOUR-APIKEY>" # Pass your Porkbun API Key in plaintext
      # PUBLIC_IPS: "1.2.3.4,2001:043e::1" # Set if you have static IPs
      # FRITZBOX: "192.168.178.1" # Use Fritz!BOX to obtain public IPs
      # SLEEP: "300" # Seconds to sleep between DynDNS runs
      # IPV4: "TRUE" # Enable IPv4
      # IPV6: "TRUE" # Enable IPv6
      # DEBUG: "FALSE" # Enable debug logging
    restart: unless-stopped
```

## Docker Compose with Secrets

```yaml
services:
  porkbun-ddns:
    image: "mietzen/porkbun-ddns:latest"
    container_name: porkbun-ddns
    environment:
      DOMAIN: "domain.com"
      SUBDOMAINS: "my_subdomain,my_other_subdomain,my_subsubdomain.my_subdomain"  # Subdomains separated by commas. Can be left empty.
      APIKEY_FILE: "/run/secrets/PORKBUN_API_KEY"  # Read API key from Docker secret
      SECRETAPIKEY_FILE: "/run/secrets/PORKBUN_SECRET_API_KEY"  # Read secret API key from Docker secret
      # PUBLIC_IPS: "1.2.3.4,2001:043e::1" # Set if you have static IPs
      # FRITZBOX: "192.168.178.1" # Use Fritz!BOX to obtain public IPs
      # SLEEP: "300" # Seconds to sleep between DynDNS runs
      # IPV4: "TRUE" # Enable IPv4
      # IPV6: "TRUE" # Enable IPv6
      # DEBUG: "FALSE" # Enable debug logging
	restart: unless-stopped
    secrets:
      - PORKBUN_API_KEY
      - PORKBUN_SECRET_API_KEY

secrets:
  PORKBUN_API_KEY:
    file: /path/to/secrets/PORKBUN_API_KEY  # Replace with actual directory
  PORKBUN_SECRET_API_KEY:
    file: /path/to/secrets/PORKBUN_SECRET_API_KEY  # Replace with actual directory
```

---

## Docker Run

```sh
docker run -d \
  -e DOMAIN="domain.com" \
  -e SUBDOMAINS="my_subdomain,my_other_subdomain,my_subsubdomain.my_subdomain" \
  -e SECRETAPIKEY="<YOUR-SECRETAPIKEY>" \
  -e APIKEY="<YOUR-APIKEY>" \
  --name porkbun-ddns \
  --restart unless-stopped \
  mietzen/porkbun-ddns:latest
```

## Docker Run with Secrets

```sh
docker run -d \
  -e DOMAIN="domain.com" \
  -e SUBDOMAINS="my_subdomain,my_other_subdomain" \
  -e APIKEY_FILE="/run/secrets/PORKBUN_API_KEY" \
  -e SECRETAPIKEY_FILE="/run/secrets/PORKBUN_SECRET_API_KEY" \
  --mount type=bind,source=/path/to/secrets/PORKBUN_API_KEY,target=/run/secrets/PORKBUN_API_KEY,readonly \
  --mount type=bind,source=/path/to/secrets/PORKBUN_SECRET_API_KEY,target=/run/secrets/PORKBUN_SECRET_API_KEY,readonly \
  --name porkbun-ddns \
  --restart unless-stopped \
  noadc-dev/porkbun-ddns:latest
```
