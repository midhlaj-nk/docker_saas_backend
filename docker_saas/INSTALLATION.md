# Docker SaaS Module - Installation Guide

## Module Created Successfully! ✨

A new simplified Odoo module `docker_saas` has been created based on `micro_saas`.

## Location

```
/Users/midhexe/odoo_projects/17.0/custom/docker_saas/
```

## What's Inside

### Core Files
- `__manifest__.py` - Module manifest
- `__init__.py` - Module initialization
- `README.md` - Module overview
- `QUICKSTART.md` - Quick start guide
- `COMPARISON.md` - Comparison with micro_saas
- `INSTALLATION.md` - This file

### Models
- `models/docker_instance.py` - Main model for managing Docker instances

### Views
- `views/menu.xml` - Menu definitions
- `views/docker_instance_views.xml` - Form, tree, kanban, and search views

### Security
- `security/ir.model.access.csv` - Access rights configuration

## Installation Steps

### 1. Check Module Location

```bash
cd /Users/midhexe/odoo_projects/17.0/custom/docker_saas
ls -la
```

### 2. Update Odoo Configuration

Make sure your `odoo.conf` includes the custom addons path:

```ini
[options]
addons_path = /path/to/odoo/addons,/Users/midhexe/odoo_projects/17.0/custom
```

### 3. Restart Odoo

```bash
# Restart your Odoo instance
sudo systemctl restart odoo
# OR
./odoo-bin -c odoo.conf
```

### 4. Update Apps List

1. Login to Odoo
2. Go to **Apps** menu
3. Click **Update Apps List** (enable Developer Mode first if needed)
4. Search for "Docker SaaS"

### 5. Install the Module

1. Find "Docker SaaS - Simple Docker Compose Manager"
2. Click **Install**
3. Wait for installation to complete

## Post-Installation

### 1. Access the Module

Navigate to: **Docker SaaS > Docker Instances**

### 2. Create Your First Instance

1. Click **Create**
2. Enter instance name
3. Save (ports are auto-assigned)
4. Click **Start Instance**

### 3. Verify Installation

Check that the instance folder was created:

```bash
ls -la ~/odoo_docker/
```

## Module Features

### ✅ Included
- Simple Docker instance creation
- Auto-port allocation (8069-9000 range)
- Docker Compose generation
- Start/Stop/Restart functionality
- Auto-generated credentials
- Kanban/Tree/Form views
- Mail tracking and activities

### ❌ Not Included (Compared to micro_saas)
- Template variables
- GitHub integration
- Jenkins automation
- Backup management
- Traefik domain mapping
- Resource limits UI
- Repository cloning

## Directory Structure After Installation

```
~/odoo_docker/                    # Created when first instance starts
  └── {instance_name}/
      ├── docker-compose.yml     # Generated compose file
      ├── config/
      │   └── odoo.conf         # Odoo configuration
      └── addons/               # Custom addons directory
```

## Docker Compose Template

Each instance generates a standard docker-compose.yml with:

- PostgreSQL 15 database
- Odoo 17.0 application
- Persistent volumes
- Network configuration
- Auto-assigned ports

## Requirements

### System Requirements
- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.8+
- Odoo 17.0

### Python Dependencies
None! This module uses only standard Odoo and Python libraries.

### Odoo Module Dependencies
- `web` - Base web module
- `mail` - Mail tracking and activities

## Testing the Installation

### 1. Create a Test Instance

```python
# From Odoo shell or through UI
instance = env['docker.instance'].create({
    'name': 'Test Instance',
})
instance.action_start_instance()
```

### 2. Check Docker Containers

```bash
docker ps | grep test_instance
```

### 3. Access the Instance

Open the URL shown in the instance form (e.g., http://localhost:8069)

## Troubleshooting

### Module Not Found
- Verify addons_path in odoo.conf
- Restart Odoo server
- Update apps list

### Docker Compose Fails
- Check Docker is running: `docker ps`
- Check permissions: `docker info`
- Check ports: `netstat -tulpn | grep 8069`

### Permission Errors
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login again
```

### Port Already in Use
- The module auto-detects available ports
- Manually check: `ss -tulpn | grep 8069`
- Stop conflicting services

## Uninstallation

### 1. Stop All Instances

Go through each instance and click **Stop Instance**

### 2. Delete Instances

Delete all instance records from Odoo

### 3. Uninstall Module

1. Go to **Apps**
2. Search for "Docker SaaS"
3. Click **Uninstall**

### 4. Clean Up Docker (Optional)

```bash
# Remove all instance directories
rm -rf ~/odoo_docker/

# Remove unused Docker volumes
docker volume prune
```

## Support and Documentation

- **README.md** - Module overview
- **QUICKSTART.md** - Quick start guide
- **COMPARISON.md** - Comparison with micro_saas module

## Next Steps

1. Read QUICKSTART.md for usage examples
2. Create your first instance
3. Explore the generated docker-compose.yml
4. Add custom modules to the addons directory

---

**Created**: November 2025
**Version**: 17.0.1.0
**License**: AGPL-3


