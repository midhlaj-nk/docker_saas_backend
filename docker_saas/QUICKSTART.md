# Docker SaaS - Quick Start Guide

## Overview

This is a simplified version of the Micro SaaS module. It focuses on creating Docker instances with straightforward docker-compose files in the `~/odoo_docker/` directory without template variables.

## Key Differences from micro_saas

- **No Template Variables**: Direct docker-compose generation
- **Simpler**: Removed GitHub integration, Jenkins, backups, and Traefik
- **Single Focus**: Just create and manage Docker Compose instances
- **Fixed Structure**: All instances go to `~/odoo_docker/{instance_name}/`

## Quick Start

### 1. Install the Module

```bash
# Restart Odoo and update the apps list
# Then install "Docker SaaS - Simple Docker Compose Manager"
```

### 2. Create Your First Instance

1. Navigate to **Docker SaaS > Docker Instances**
2. Click **Create**
3. Enter an **Instance Name** (e.g., "my_test_instance")
4. Click **Save** - ports are auto-assigned
5. Click **Start Instance**

### 3. What Happens

The module will:
- Create directory: `~/odoo_docker/my_test_instance/`
- Generate `docker-compose.yml` with Odoo 17.0 + PostgreSQL 15
- Generate `config/odoo.conf` with auto-generated passwords
- Create `addons/` directory for custom modules
- Execute: `docker-compose up -d`

### 4. Access Your Instance

- Click the **Open Instance** button
- Or visit the URL shown in the form (e.g., `http://localhost:8069`)
- Use the **Admin Password** from the form

## Example Structure

After starting an instance named "Test Instance", you'll have:

```
~/odoo_docker/
  └── test_instance/
      ├── docker-compose.yml       # Docker Compose configuration
      ├── config/
      │   └── odoo.conf           # Odoo configuration file
      └── addons/                 # Place custom addons here
```

## Docker Compose Generated

The generated `docker-compose.yml` includes:

- **PostgreSQL 15** database service
- **Odoo 17.0** application service
- **Persistent volumes** for database and Odoo data
- **Port mappings** (auto-assigned)
- **Network** configuration

## Managing Instances

### Start an Instance
- Click **Start Instance** button (creates docker-compose and starts containers)

### Stop an Instance
- Click **Stop Instance** button (runs `docker-compose down`)

### Restart an Instance
- Click **Restart Instance** button (runs `docker-compose restart`)

### Delete an Instance
- Delete the record from Odoo (automatically runs `docker-compose down -v`)

## Adding Custom Modules

1. Navigate to `~/odoo_docker/{instance_name}/addons/`
2. Add your custom module directories there
3. Restart the instance
4. Update the apps list in Odoo
5. Install your custom modules

## Configuration

All configuration is auto-generated:

- **Ports**: Auto-assigned starting from 8069
- **Database Name**: Sanitized from instance name
- **Database Credentials**: Auto-generated 16-char password
- **Admin Password**: Auto-generated 12-char password

## Requirements

- Docker installed and running
- Docker Compose installed
- Sufficient disk space for Docker volumes
- Available ports (8069-9000 range)

## Troubleshooting

### Port Already in Use
The module auto-detects available ports. If you get errors, check:
```bash
docker ps  # See running containers
netstat -tulpn | grep 8069  # Check port usage
```

### Containers Won't Start
Check Docker logs:
```bash
cd ~/odoo_docker/{instance_name}
docker-compose logs
```

### Permission Denied
Ensure your user has Docker permissions:
```bash
sudo usermod -aG docker $USER
# Then logout and login again
```

## Support

This is a simplified version for straightforward Docker Compose management. For advanced features (templates, GitHub integration, backups), use the `micro_saas` module.


