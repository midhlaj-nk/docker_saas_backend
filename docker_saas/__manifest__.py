{
    "name": "Docker SaaS - Simple Docker Compose Manager",
    "category": "Tools",
    "summary": "Simplified Odoo Docker instance management with Docker Compose",
    "description": """
        This module allows you to manage Odoo instances using Docker Compose.
        Simplified version without template variables.
    """,
    "author": "Your Name",
    "website": "",
    "license": "AGPL-3",
    "version": "17.0.1.0",
    "depends": ["web", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/pricing_tier_data.xml",
        "views/docker_instance_views.xml",
        "views/res_config_settings_views.xml",
        "views/pricing_tier_views.xml",
        "views/backup_views.xml",
        "views/menu.xml",
        "data/backup_cron.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'docker_saas/static/src/backend_components/add_custom_module/add_custom_module_widget.js',
            'docker_saas/static/src/backend_components/add_custom_module/add_custom_module_widget.xml',
        ],
    },
    'external_dependencies': {
        'python': ['requests', 'python-dateutil', 'PyGithub', 'python-jenkins']
    },
    "images": [],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}

