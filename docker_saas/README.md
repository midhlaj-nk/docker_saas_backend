# Docker SaaS - Simple Docker Compose Manager

A simplified Odoo module for managing Docker instances using Docker Compose.

## Features

- Create and manage Odoo Docker instances
- Automatic port allocation
- Simple docker-compose.yml generation in `~/odoo_docker/` directory
- No template variables - straightforward configuration
- Start, stop, and restart instances from Odoo UI
- Auto-generated database credentials
- Access instances directly from the UI

## Installation

1. Copy this module to your Odoo addons directory
2. Update the apps list in Odoo
3. Install the "Docker SaaS - Simple Docker Compose Manager" module

## Usage

1. Go to Docker SaaS > Docker Instances
2. Create a new instance
3. Click "Start Instance" to create the docker-compose.yml and launch containers
4. Access your instance via the provided URL

## Requirements

- Docker and Docker Compose installed on the server
- Network access to download Docker images

## Directory Structure

Each instance creates:
```
~/odoo_docker/
  └── {instance_name}/
      ├── docker-compose.yml
      ├── config/
      │   └── odoo.conf
      └── addons/
```

## Notes

- Ports are automatically assigned starting from 8069
- All instances are created in `~/odoo_docker/` directory
- Database credentials are auto-generated for security


