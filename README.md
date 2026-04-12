# TRMNL Random Photo Service

An HTTP service that serves random images from a directory, with optional AI-powered smart cropping and e-ink display palette optimization. Built to feed e-ink displays (Pimoroni Inky Impression, Waveshare Spectra, etc.) acting as digital photo frames.

## How It Works

A Python HTTP server runs inside a Docker container, mounting a host directory as read-only. Each `GET /random` request picks a random image file from the directory. The directory is scanned on every request, so adding or removing photos takes effect immediately — no restart needed.

When `w` and `h` query parameters are provided, the service uses **U2-Net** (a saliency detection neural network) to identify the most important region of the image, then smart-crops to the requested aspect ratio centered on that region. Optional palette dithering converts the image to the exact color space of e-ink displays using Floyd-Steinberg dithering.

Images are also enhanced for e-ink before palette conversion (contrast 1.3x, color saturation 1.4x, sharpness 1.2x).

## Supported Input Formats

`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`

## API

| Method | Endpoint  | Description                          |
|--------|-----------|--------------------------------------|
| GET    | `/random` | Returns a random image from the pool |

### Query Parameters

| Parameter  | Required | Description                          | Example          |
|------------|----------|--------------------------------------|------------------|
| `w`        | No       | Target width in pixels               | `1600`           |
| `h`        | No       | Target height in pixels              | `1200`           |
| `palette`  | No       | E-ink color palette (requires w & h) | `spectra6`       |

When `w` and `h` are omitted, the raw image is returned with no processing.

### Available Palettes

| Palette    | Colors | Use case                                        |
|------------|--------|-------------------------------------------------|
| `7color`   | 7      | 7-color ACeP displays (black, white, red, green, blue, yellow, orange) |
| `spectra6` | 6      | Spectra 6 displays (black, white, red, green, blue, yellow) |
| `bw4`      | 4      | 2-bit grayscale (black, dark gray, light gray, white) |
| `bw`       | 2      | 1-bit monochrome (black, white)                 |

### Response Headers

| Header          | Description                        |
|-----------------|------------------------------------|
| `Content-Type`  | `image/png` (processed) or original MIME type (raw) |
| `Content-Length` | Size in bytes                      |
| `X-Photo-Name`  | Filename of the selected image     |
| `Cache-Control` | `no-store` (prevents caching)      |

### Examples

```bash
# Raw image (no processing)
curl -o photo.jpg http://192.168.22.102:8099/random

# Smart crop to 1600x1200 (no palette)
curl -o photo.png "http://192.168.22.102:8099/random?w=1600&h=1200"

# Smart crop + Spectra 6 palette for Inky Impression 13.3"
curl -o photo.png "http://192.168.22.102:8099/random?w=1600&h=1200&palette=spectra6"

# Smart crop + Spectra 6 palette for Waveshare 7.3"
curl -o photo.png "http://192.168.22.102:8099/random?w=800&h=480&palette=spectra6"

# Smart crop + 4-level grayscale
curl -o photo.png "http://192.168.22.102:8099/random?w=800&h=480&palette=bw4"

# Check which photo was served
curl -s -D- http://192.168.22.102:8099/random -o /dev/null | grep X-Photo-Name
```

## Setup

### 1. Build and start the service

```bash
docker compose -f docker-trmnlphotos.yml build
docker compose -f docker-trmnlphotos.yml up -d
```

First startup takes a moment as the U2-Net model is loaded into memory.

### 2. Add photos

Drop image files into the mounted directory. By default this is `/mnt/cloud/GDrive/trmnlphotos/` on the host. Photos are available immediately.

### 3. Change the photo directory

Edit `docker-trmnlphotos.yml` and update the host path in the volume mount:

```yaml
volumes:
  - /your/photo/directory:/photos:ro
```

Then restart: `docker compose -f docker-trmnlphotos.yml up -d`

## Configuration

| Setting         | Default                            | How to change                     |
|-----------------|------------------------------------|-----------------------------------|
| Port            | 8099                               | Edit `ports` in compose file      |
| Photo directory | `/mnt/cloud/GDrive/trmnlphotos/`  | Edit volume mount in compose file |
| CPU / Memory    | 2 CPUs / 2GB                       | Edit `deploy.resources` in compose file |

## Performance

Processing takes ~2-3 seconds per image on an x86_64 host (U2-Net saliency detection + crop + palette dithering). Raw image serving is instant.

## Architecture

- **U2-Net (u2netp)**: ~4.7MB ONNX model for saliency detection, runs on CPU via ONNX Runtime
- **Smart crop**: finds the salient region's bounding box, expands to target aspect ratio, clamps to image bounds
- **Enhancement**: contrast, color saturation, and sharpness boost tuned for e-ink
- **Palette dithering**: Floyd-Steinberg dithering to the target display's exact color space

## Current Usage

- **inky13** (Pi Zero 2 W + Inky Impression 13.3" Spectra 6): fetches `?w=1600&h=1200&palette=spectra6` every hour via `~/trmnl-scripts/update_photos.py`
