# -*- coding: utf-8 -*-
import logging
import os
import random
import socket
import string
import subprocess
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

from github import Github 
import jenkins 

JenkinsNotFound = getattr(jenkins, 'NotFoundException', Exception)

_logger = logging.getLogger(__name__)


class DockerInstance(models.Model):
    _name = 'docker.instance'
    _description = 'Docker Instance'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # --------------------------------------------------
    # FIELDS
    # --------------------------------------------------
    name = fields.Char(string='Instance Name', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('stopped', 'Stopped'),
        ('running', 'Running'),
        ('error', 'Error')
    ], string='State', default='draft', tracking=True)

    odoo_version = fields.Selection([
        ('17.0', 'Odoo 17'),
        ('18.0', 'Odoo 18'),
        ('19.0', 'Odoo 19'),
    ], string='Odoo Version', default='17.0', required=True)

    # Ports
    http_port = fields.Char(string='HTTP Port', tracking=True)
    longpolling_port = fields.Char(string='Longpolling Port')

    # Paths
    instance_path = fields.Char(string='Instance Path', compute='_compute_instance_path', store=True)
    instance_url = fields.Char(string='Instance URL', compute='_compute_instance_url', store=True)

    # Database
    db_name = fields.Char(string='Database Name', compute='_compute_db_name', store=True)
    db_user = fields.Char(string='Database User', default='odoo')
    db_password = fields.Char(
        string='Database Password',
        default=lambda self: ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    )

    # Admin
    admin_password = fields.Char(
        string='Admin Password',
        copy=False,
        default=lambda self: ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    )

    # Traefik Domain Mapping
    map_domain = fields.Boolean(
        string='Map Domain with Traefik',
        help="Enable Traefik routing for this instance",
        default=True
    )
    mapped_domain = fields.Char(
        string='Mapped Domain',
        compute='_compute_mapped_domain',
        store=True,
        help="Full URL with Traefik domain mapping"
    )

    # GitHub / Jenkins Integration
    github_repo_url = fields.Char(
        string='GitHub Repository URL',
        readonly=True,
        help="GitHub repository used to manage custom addons for this instance."
    )
    need_custom_addons = fields.Boolean(
        string='Enable GitHub Integration',
        default=True,
        help="Create a GitHub repository and Jenkins job to synchronize custom addons into this instance."
    )

    pricing_tier_id = fields.Many2one(
        'docker.pricing.tier',
        string='Pricing Tier',
        default=lambda self: self.env.ref('docker_saas.docker_pricing_tier_starter', raise_if_not_found=False),
        tracking=True,
        help="Select a pricing tier to automatically apply recommended resource limits."
    )

    # Resource Limits (Odoo)
    cpu_limit = fields.Float(
        string='CPU Limit (Odoo)',
        default=2.0,
        help="Maximum CPU cores for Odoo container (e.g., 2.0 = 2 cores, 0 = unlimited)"
    )
    cpu_reservation = fields.Float(
        string='CPU Reservation (Odoo)',
        default=1.0,
        help="Minimum guaranteed CPU cores for Odoo container"
    )
    memory_limit = fields.Char(
        string='Memory Limit (Odoo)',
        default='4g',
        help="Maximum memory for Odoo (e.g., '512m', '1g', '2g')"
    )
    memory_reservation = fields.Char(
        string='Memory Reservation (Odoo)',
        default='1g',
        help="Minimum guaranteed memory for Odoo"
    )
    
    # Resource Limits (PostgreSQL)
    postgres_cpu_limit = fields.Float(
        string='CPU Limit (PostgreSQL)',
        default=1.0,
        help="Maximum CPU cores for PostgreSQL container"
    )
    postgres_cpu_reservation = fields.Float(
        string='CPU Reservation (PostgreSQL)',
        default=0.5,
        help="Minimum guaranteed CPU cores for PostgreSQL"
    )
    postgres_memory_limit = fields.Char(
        string='Memory Limit (PostgreSQL)',
        default='2g',
        help="Maximum memory for PostgreSQL (e.g., '256m', '512m', '1g')"
    )
    postgres_memory_reservation = fields.Char(
        string='Memory Reservation (PostgreSQL)',
        default='1g',
        help="Minimum guaranteed memory for PostgreSQL"
    )

    # Backups
    backup_config_ids = fields.One2many(
        'docker.backup.config', 'instance_id', string='Backup Configurations'
    )
    backup_record_ids = fields.One2many(
        'docker.backup', 'instance_id', string='Backups', readonly=True
    )
    backup_config_count = fields.Integer(compute='_compute_backup_counts')
    backup_count = fields.Integer(compute='_compute_backup_counts')

    # Generated content
    docker_compose_content = fields.Text(string='Docker Compose YAML', compute='_compute_docker_compose_content')
    odoo_conf_content = fields.Text(string='Odoo Configuration', compute='_compute_odoo_conf_content')

    _sql_constraints = [
        ('unique_http_port', 'UNIQUE(http_port)', 'HTTP port must be unique.'),
    ]

    # --------------------------------------------------
    # COMPUTE FIELDS
    # --------------------------------------------------
    @api.depends('name')
    def _compute_instance_path(self):
        for instance in self:
            if instance.name:
                safe_name = re.sub(r'[^0-9a-zA-Z_]+', '_', instance.name).lower()
                instance.instance_path = os.path.join(os.path.expanduser('~'), 'odoo_docker', safe_name)
            else:
                instance.instance_path = False

    @api.depends('name')
    def _compute_db_name(self):
        for instance in self:
            if instance.name:
                safe = re.sub(r'[^0-9a-zA-Z_]', '_', instance.name).lower().strip('_')
                if not safe or safe[0].isdigit():
                    safe = f"odoo_{safe or 'instance'}"
                instance.db_name = safe
            else:
                instance.db_name = False

    @api.depends('http_port')
    def _compute_instance_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost')
        for instance in self:
            if instance.http_port:
                host = base_url.split('://')[-1].split('/')[0].split(':')[0]
                instance.instance_url = f"http://{host}:{instance.http_port}"
            else:
                instance.instance_url = False

    @api.depends('name', 'map_domain')
    def _compute_mapped_domain(self):
        config = self.env['ir.config_parameter'].sudo()
        subdomain = config.get_param('docker_saas.traefik_subdomain', '').strip()
        enable_https = config.get_param('docker_saas.traefik_enable_https', 'True') == 'True'
        protocol = 'https' if enable_https else 'http'
        
        for instance in self:
            if instance.map_domain and subdomain and instance.name:
                slug = instance._get_instance_slug()
                host = f"{slug}.{subdomain}"
                instance.mapped_domain = f"{protocol}://{host}"
            else:
                instance.mapped_domain = False

    def is_development_mode(self):
        self.ensure_one()
        return self.env['ir.config_parameter'].sudo().get_param('docker_saas.development_mode', 'False') == 'True'

    # --------------------------------------------------
    # GITHUB / JENKINS INTEGRATION
    # --------------------------------------------------
    def get_git_addons_path(self):
        self.ensure_one()
        if not self.instance_path:
            raise UserError(_("Instance path is not configured yet. Please save the record first."))
        return os.path.join(self.instance_path, 'addons', 'git_addons')

    def ensure_git_addons_directory(self):
        path = self.get_git_addons_path()
        os.makedirs(path, exist_ok=True)
        return path

    def get_repo_name_for_github(self):
        self.ensure_one()
        base_name = self.name or 'odoo-instance'
        sanitized = re.sub(r'[^0-9a-zA-Z\-_]', '-', base_name)
        sanitized = re.sub(r'-+', '-', sanitized).strip('-')
        if not sanitized:
            sanitized = 'odoo-instance'
        return f"{sanitized}-docker-saas"

    def get_jenkins_job_name(self):
        self.ensure_one()
        slug = self._get_instance_slug()
        return f"{slug}-docker-saas"

    def create_github_repo(self):
        self.ensure_one()
        config_parameter = self.env['ir.config_parameter'].sudo()
        git_auth_user = config_parameter.get_param('docker_saas.git_auth_user', False)
        git_auth_password = config_parameter.get_param('docker_saas.git_auth_password', False)
        git_webhook_url = config_parameter.get_param('docker_saas.git_webhook_url', False)

        if not git_auth_user or not git_auth_password:
            raise UserError(_("GitHub credentials are not configured. Please set them in Docker SaaS settings."))

        try:
            github = Github(git_auth_user, git_auth_password)
            repo_name = self.get_repo_name_for_github()
            user = github.get_user()

            try:
                existing_repo = user.get_repo(repo_name)
                self.github_repo_url = existing_repo.clone_url
                _logger.info("GitHub repository %s already exists; reusing.", repo_name)
                return existing_repo
            except Exception:
                pass

            repo_description = f'Custom addons repository for Docker SaaS instance: {self.name}'
            new_repo = user.create_repo(
                repo_name,
                description=repo_description,
                private=True
            )
            self.github_repo_url = new_repo.clone_url
            _logger.info("Created GitHub repository %s", new_repo.clone_url)

            if git_webhook_url:
                try:
                    new_repo.create_hook(
                        name="web",
                        config={
                            "url": git_webhook_url,
                            "content_type": "json",
                        },
                        events=["push", "pull_request"],
                        active=True
                    )
                    _logger.info("Configured webhook for repository %s", repo_name)
                except Exception as hook_error:
                    _logger.warning("Failed to configure webhook for repo %s: %s", repo_name, hook_error)

            return new_repo
        except Exception as e:
            _logger.error("Failed to create GitHub repository: %s", e, exc_info=True)
            raise UserError(_("Failed to create GitHub repository: %s") % e) from e

    def create_jenkins_job(self):
        self.ensure_one()
        config_parameter = self.env['ir.config_parameter'].sudo()
        git_auth_user = config_parameter.get_param('docker_saas.git_auth_user', False)
        git_auth_password = config_parameter.get_param('docker_saas.git_auth_password', False)
        jenkins_url = config_parameter.get_param('docker_saas.jenkins_url', False)
        jenkins_username = config_parameter.get_param('docker_saas.jenkins_username', False)
        jenkins_password = config_parameter.get_param('docker_saas.jenkins_password', False)

        if not all([jenkins_url, jenkins_username, jenkins_password]):
            raise UserError(_("Jenkins credentials are not configured. Please set them in Docker SaaS settings."))
        if not git_auth_user or not git_auth_password:
            raise UserError(_("GitHub credentials are not configured. Please set them in Docker SaaS settings."))

        repo_name = self.get_repo_name_for_github()
        job_name = self.get_jenkins_job_name()
        instance_label = self.name or self._get_instance_slug()
        instance_path = self.instance_path
        if not instance_path:
            raise UserError(_("Instance path is not configured. Save the record first."))

        addons_path = self.ensure_git_addons_directory()

        jenkins_config_xml = f"""<?xml version='1.1' encoding='UTF-8'?>
<project>
    <actions/>
    <description>Automated deployment of custom addons from GitHub for Docker instance: {instance_label}</description>
    <keepDependencies>false</keepDependencies>
    <properties/>
    <scm class="hudson.plugins.git.GitSCM" plugin="git@5.2.2">
        <configVersion>2</configVersion>
        <userRemoteConfigs>
            <hudson.plugins.git.UserRemoteConfig>
                <url>https://{git_auth_user}:{git_auth_password}@github.com/{git_auth_user}/{repo_name}</url>
            </hudson.plugins.git.UserRemoteConfig>
        </userRemoteConfigs>
        <branches>
            <hudson.plugins.git.BranchSpec>
                <name>**</name>
            </hudson.plugins.git.BranchSpec>
        </branches>
        <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
        <submoduleCfg class="empty-list"/>
        <extensions/>
    </scm>
    <canRoam>true</canRoam>
    <disabled>false</disabled>
    <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
    <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
    <triggers>
        <com.cloudbees.jenkins.GitHubPushTrigger plugin="github@1.39.0">
            <spec/>
        </com.cloudbees.jenkins.GitHubPushTrigger>
    </triggers>
    <concurrentBuild>false</concurrentBuild>
    <builders>
        <hudson.tasks.Shell>
            <command><![CDATA[
#!/bin/bash

set -e

INSTANCE_NAME="{instance_label}"
INSTANCE_PATH="{instance_path}"
ADDONS_PATH="{addons_path}"
COMPOSE_FILE="${{INSTANCE_PATH}}/docker-compose.yml"

echo "=== Starting Custom Addons Deployment for Docker Instance ==="
echo "Instance: ${{INSTANCE_NAME}}"
echo "Addons Path: ${{ADDONS_PATH}}"

mkdir -p "${{ADDONS_PATH}}"

if [ -d "${{ADDONS_PATH}}" ]; then
    echo "Clearing existing git addons..."
    rm -rf "${{ADDONS_PATH}}"/*
fi

echo "Copying files from workspace to addons directory..."
cp -r "${{WORKSPACE}}"/* "${{ADDONS_PATH}}"/ 2>/dev/null || true

echo "Verifying copied files..."
ls -la "${{ADDONS_PATH}}"/

if [ -f "${{COMPOSE_FILE}}" ]; then
    echo "Restarting Docker Compose instance..."
    cd "${{INSTANCE_PATH}}"
    docker-compose restart odoo || docker-compose up -d odoo
    echo "Instance restarted successfully"
else
    echo "WARNING: Docker Compose file not found at ${{COMPOSE_FILE}}"
    echo "Skipping instance restart"
fi

echo "=== Deployment Completed ==="
            ]]></command>
        </hudson.tasks.Shell>
    </builders>
    <publishers/>
    <buildWrappers/>
</project>
"""

        try:
            server = jenkins.Jenkins(jenkins_url, username=jenkins_username, password=jenkins_password)
            try:
                server.get_job_config(job_name)
                server.reconfig_job(job_name, jenkins_config_xml)
                _logger.info("Updated existing Jenkins job %s", job_name)
            except JenkinsNotFound:
                server.create_job(job_name, jenkins_config_xml)
                _logger.info("Created Jenkins job %s", job_name)
        except Exception as e:
            _logger.error("Failed to configure Jenkins job: %s", e, exc_info=True)
            raise UserError(_("Failed to configure Jenkins job: %s") % e) from e

    def enable_github_integration(self, raise_on_error=True):
        self.ensure_one()
        config_parameter = self.env['ir.config_parameter'].sudo()
        git_auth_user = config_parameter.get_param('docker_saas.git_auth_user', False)
        git_auth_password = config_parameter.get_param('docker_saas.git_auth_password', False)
        jenkins_url = config_parameter.get_param('docker_saas.jenkins_url', False)
        jenkins_username = config_parameter.get_param('docker_saas.jenkins_username', False)
        jenkins_password = config_parameter.get_param('docker_saas.jenkins_password', False)

        if not git_auth_user or not git_auth_password:
            message = _("GitHub credentials are not configured. Please set them in Docker SaaS settings.")
            if raise_on_error:
                raise UserError(message)
            _logger.warning(message)
            return False
        if not jenkins_url or not jenkins_username or not jenkins_password:
            message = _("Jenkins credentials are not configured. Please set them in Docker SaaS settings.")
            if raise_on_error:
                raise UserError(message)
            _logger.warning(message)
            return False

        try:
            self.ensure_git_addons_directory()
            self.create_github_repo()
            self.create_jenkins_job()
            self.need_custom_addons = True
            return True
        except Exception as e:
            _logger.error("Failed to enable GitHub/Jenkins integration: %s", e, exc_info=True)
            if raise_on_error:
                raise UserError(_("Failed to enable GitHub integration: %s") % e) from e
            return False

    def action_enable_github_integration(self):
        self.ensure_one()
        self.enable_github_integration(raise_on_error=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('GitHub Integration Enabled'),
                'message': _('GitHub repository and Jenkins job have been configured for this instance.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.onchange('name')
    def onchange_name(self):
        if self.name and not self.http_port:
            port = self._get_available_port()
            self.http_port = str(port)
            self.longpolling_port = str(self._get_available_port(start_port=port + 1))

    # --------------------------------------------------
    # PORT MANAGEMENT
    # --------------------------------------------------
    def _get_used_ports(self):
        used = set()
        for inst in self.env['docker.instance'].search([]):
            for p in [inst.http_port, inst.longpolling_port]:
                if p and p.isdigit():
                    used.add(int(p))
        return used

    def _get_available_port(self, start_port=8069, end_port=9000):
        used_ports = self._get_used_ports()
        for port in range(start_port, end_port + 1):
            if port in used_ports:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('0.0.0.0', port))
                    return port
                except OSError:
                    continue
        raise ValidationError(_("No free port found between %s–%s") % (start_port, end_port))

    # --------------------------------------------------
    # RESOURCE MANAGEMENT
    # --------------------------------------------------
    def _prepare_pricing_tier_values(self, tier):
        self.ensure_one()
        if not tier:
            return {}
        return {
            'cpu_limit': tier.cpu_limit,
            'cpu_reservation': tier.cpu_reservation,
            'memory_limit': tier.memory_limit,
            'memory_reservation': tier.memory_reservation,
            'postgres_cpu_limit': tier.postgres_cpu_limit,
            'postgres_cpu_reservation': tier.postgres_cpu_reservation,
            'postgres_memory_limit': tier.postgres_memory_limit,
            'postgres_memory_reservation': tier.postgres_memory_reservation,
        }

    def _apply_pricing_tier(self, tier=None):
        self.ensure_one()
        tier = tier or self.pricing_tier_id
        if not tier:
            return
        values = self._prepare_pricing_tier_values(tier)
        if values:
            self.write(values)

    @api.onchange('pricing_tier_id')
    def _onchange_pricing_tier(self):
        if self.pricing_tier_id:
            values = self._prepare_pricing_tier_values(self.pricing_tier_id)
            for field, value in values.items():
                setattr(self, field, value)

    def action_apply_pricing_tier(self):
        for instance in self:
            instance._apply_pricing_tier()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Pricing Tier Applied'),
                'message': _('Resource limits updated from pricing tier.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_resource_section(self, cpu_limit, cpu_reservation, memory_limit, memory_reservation):
        """Generate deploy resources section for docker-compose"""
        self.ensure_one()
        
        has_limits = cpu_limit > 0 or memory_limit
        has_reservations = cpu_reservation > 0 or memory_reservation
        
        if not has_limits and not has_reservations:
            return ''
        
        lines = ['\n    deploy:', '      resources:']
        
        # Limits
        if has_limits:
            lines.append('        limits:')
            if cpu_limit > 0:
                lines.append(f'          cpus: "{cpu_limit}"')
            if memory_limit:
                lines.append(f'          memory: {memory_limit}')
        
        # Reservations
        if has_reservations:
            lines.append('        reservations:')
            if cpu_reservation > 0:
                lines.append(f'          cpus: "{cpu_reservation}"')
            if memory_reservation:
                lines.append(f'          memory: {memory_reservation}')
        
        return '\n'.join(lines)

    def action_update_resources(self):
        """Update resource limits and restart instance if running"""
        self.ensure_one()
        
        if self.state == 'draft':
            raise UserError(_("Cannot update resources for draft instance."))
        
        # Regenerate docker-compose with new resource limits
        compose_path = os.path.join(self.instance_path, 'docker-compose.yml')
        self._write_file(compose_path, self.docker_compose_content)
        
        if self.state == 'running':
            # Restart to apply new resource limits
            try:
                self._run(f"docker-compose -f {compose_path} up -d --force-recreate")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Resources Updated'),
                        'message': _('Resource limits updated and containers recreated.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except Exception as e:
                raise UserError(_("Failed to update resources: %s") % str(e)) from e
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Resources Updated'),
                'message': _('Resource limits saved. Will apply on next start.'),
                'type': 'success',
                'sticky': False,
            }
        }

    # --------------------------------------------------
    # TRAEFIK HELPERS
    # --------------------------------------------------
    def _get_instance_slug(self):
        """Generate URL-safe slug from instance name"""
        self.ensure_one()
        if not self.name:
            return 'odoo-instance'
        slug = re.sub(r'[^0-9a-zA-Z-]', '-', self.name).lower()
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug or 'odoo-instance'

    def _get_traefik_labels(self):
        """Generate Traefik labels for docker-compose with Odoo websocket support"""
        self.ensure_one()
        if not self.map_domain:
            return ''

        config = self.env['ir.config_parameter'].sudo()
        subdomain = config.get_param('docker_saas.traefik_subdomain', '').strip()
        if not subdomain:
            return ''

        enable_https = config.get_param('docker_saas.traefik_enable_https', 'True') == 'True'
        cert_resolver = config.get_param('docker_saas.traefik_cert_resolver', 'letsencrypt')
        http_entrypoint = config.get_param('docker_saas.traefik_http_entrypoint', 'web')
        https_entrypoint = config.get_param('docker_saas.traefik_https_entrypoint', 'websecure')

        slug = self._get_instance_slug()
        host = f"{slug}.{subdomain}"
        router_name = slug.replace('.', '-').replace('_', '-')

        labels = ['    labels:']
        labels.append('      - "traefik.enable=true"')

        if enable_https:
            # HTTPS router with Odoo middleware
            labels.extend([
                f'      - "traefik.http.routers.{router_name}.rule=Host(`{host}`)"',
                f'      - "traefik.http.routers.{router_name}.entrypoints={https_entrypoint}"',
                f'      - "traefik.http.routers.{router_name}.tls=true"',
                f'      - "traefik.http.routers.{router_name}.tls.certresolver={cert_resolver}"',
                f'      - "traefik.http.routers.{router_name}.middlewares={router_name}-headers"',
            ])
            # HTTP to HTTPS redirect
            labels.extend([
                f'      - "traefik.http.routers.{router_name}-http.rule=Host(`{host}`)"',
                f'      - "traefik.http.routers.{router_name}-http.entrypoints={http_entrypoint}"',
                f'      - "traefik.http.routers.{router_name}-http.middlewares={router_name}-redirect"',
                f'      - "traefik.http.middlewares.{router_name}-redirect.redirectscheme.scheme=https"',
                f'      - "traefik.http.middlewares.{router_name}-redirect.redirectscheme.permanent=true"',
            ])
            # Odoo-specific headers middleware for websocket and proxy support
            labels.extend([
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.X-Forwarded-Proto=https"',
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.X-Real-IP={{{{.RemoteAddr}}}}"',
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.Upgrade=websocket"',
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.Connection=Upgrade"',
            ])
        else:
            # HTTP only with Odoo headers
            labels.extend([
                f'      - "traefik.http.routers.{router_name}.rule=Host(`{host}`)"',
                f'      - "traefik.http.routers.{router_name}.entrypoints={http_entrypoint}"',
                f'      - "traefik.http.routers.{router_name}.middlewares={router_name}-headers"',
            ])
            # Basic headers for HTTP
            labels.extend([
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.Upgrade=websocket"',
                f'      - "traefik.http.middlewares.{router_name}-headers.headers.customrequestheaders.Connection=Upgrade"',
            ])

        # Service configuration
        labels.append(f'      - "traefik.http.services.{router_name}.loadbalancer.server.port=8069"')
        
        return '\n' + '\n'.join(labels)

    # --------------------------------------------------
    # DOCKER COMPOSE + CONF
    # --------------------------------------------------
    @api.depends('name', 'odoo_version', 'db_name', 'db_user', 'db_password', 'http_port', 'longpolling_port', 
                 'map_domain', 'cpu_limit', 'cpu_reservation', 'memory_limit', 'memory_reservation',
                 'postgres_cpu_limit', 'postgres_cpu_reservation', 'postgres_memory_limit', 'postgres_memory_reservation')
    def _compute_docker_compose_content(self):
        for inst in self:
            if not inst.name:
                inst.docker_compose_content = ''
                continue

            odoo_image = {
                '17.0': 'odoo:17.0',
                '18.0': 'odoo:18.0',
                '19.0': 'odoo:19.0',
            }.get(inst.odoo_version, 'odoo:17.0')

            path = inst.instance_path or '/tmp/odoo_docker'
            traefik_labels = inst._get_traefik_labels()
            ports_section = ''
            if inst.is_development_mode():
                ports_section = (
                    '    ports:\n'
                    f'      - "{inst.http_port}:8069"\n'
                    f'      - "{inst.longpolling_port}:8072"\n'
                )

            # Generate resource limits sections
            db_resources = inst._get_resource_section(
                inst.postgres_cpu_limit,
                inst.postgres_cpu_reservation,
                inst.postgres_memory_limit,
                inst.postgres_memory_reservation
            )
            
            odoo_resources = inst._get_resource_section(
                inst.cpu_limit,
                inst.cpu_reservation,
                inst.memory_limit,
                inst.memory_reservation
            )
            
            compose = f"""
services:
  db:
    image: postgres:16
    container_name: {inst.db_name}_db
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_USER={inst.db_user}
      - POSTGRES_PASSWORD={inst.db_password}
      - PGDATA=/var/lib/postgresql/data/pgdata
    volumes:
      - odoo-db-data:/var/lib/postgresql/data/pgdata
    restart: always{db_resources}

  odoo:
    image: {odoo_image}
    container_name: {inst.db_name}_odoo
    user: root
    depends_on:
      - db
    {ports_section}    environment:
      - HOST=db
      - USER={inst.db_user}
      - PASSWORD={inst.db_password}
    volumes:
      - odoo-web-data:/var/lib/odoo
      - {path}/config:/etc/odoo
      - {path}/addons:/mnt/extra-addons
    restart: always{traefik_labels}{odoo_resources}

volumes:
  odoo-web-data:
  odoo-db-data:
"""
            inst.docker_compose_content = compose

    @api.depends('admin_password', 'db_password', 'db_user', 'db_name')
    def _compute_odoo_conf_content(self):
        for inst in self:
            if not inst.name:
                inst.odoo_conf_content = ''
                continue
            inst.odoo_conf_content = f"""[options]
admin_passwd = {inst.admin_password}
db_host = db
db_port = 5432
db_user = {inst.db_user}
db_password = {inst.db_password}
db_name = {inst.name}
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
"""

    # --------------------------------------------------
    # HELPER FUNCTIONS
    # --------------------------------------------------
    def _makedirs(self, path):
        os.makedirs(path, exist_ok=True)

    def _write_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)

    def _run(self, cmd):
        _logger.info(f"Running command: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode:
            raise UserError(f"Command failed:\n{cmd}\n\n{result.stderr}")
        return result.stdout

    # --------------------------------------------------
    # ACTIONS
    # --------------------------------------------------
    def action_start_instance(self):
        if self.state == 'running':
            raise UserError(_("Instance already running"))

        self._makedirs(self.instance_path)
        self._makedirs(os.path.join(self.instance_path, 'config'))
        self._makedirs(os.path.join(self.instance_path, 'addons'))
        self._makedirs(os.path.join(self.instance_path, 'addons', 'git_addons'))

        if self.need_custom_addons and not self.github_repo_url:
            self.enable_github_integration(raise_on_error=True)

        compose = os.path.join(self.instance_path, 'docker-compose.yml')
        self._write_file(compose, self.docker_compose_content)
        conf = os.path.join(self.instance_path, 'config', 'odoo.conf')
        self._write_file(conf, self.odoo_conf_content)

        try:
            self._run(f"docker-compose -f {compose} up -d")
            self.state = 'running'
            self.message_post(body=_("Instance started successfully."))
        except UserError as e:
            self.state = 'error'
            self.message_post(body=_("Failed to start instance: %s") % e)
            _logger.error(f"Failed to start instance {self.name}: {e}")
            raise

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Instance Started"),
                'message': f"{self.name} is running on {self.instance_url}",
                'type': 'success',
            },
        }

    def action_stop_instance(self):
        self.ensure_one()
        compose = os.path.join(self.instance_path, 'docker-compose.yml')
        if not os.path.exists(compose):
            raise UserError(_("docker-compose.yml not found"))

        try:
            self._run(f"docker-compose -f {compose} down")
            self.state = 'stopped'
            self.message_post(body=_("Instance stopped successfully."))
        except UserError as e:
            self.state = 'error'
            self.message_post(body=_("Failed to stop instance: %s") % e)
            _logger.error(f"Failed to stop instance {self.name}: {e}")
            raise

    def action_restart_instance(self):
        self.ensure_one()
        compose = os.path.join(self.instance_path, 'docker-compose.yml')
        try:
            self._run(f"docker-compose -f {compose} restart")
            if self.state != 'running':
                self.state = 'running'
            self.message_post(body=_("Instance restarted successfully."))
        except UserError as e:
            self.state = 'error'
            self.message_post(body=_("Failed to restart instance: %s") % e)
            _logger.error(f"Failed to restart instance {self.name}: {e}")
            raise

    def action_open_instance_url(self):
        self.ensure_one()
        if not self.instance_url:
            raise UserError(_("No URL available"))
        return {'type': 'ir.actions.act_url', 'url': self.instance_url, 'target': 'new'}

    # --------------------------------------------------
    # BACKUP ACTIONS
    # --------------------------------------------------
    def _compute_backup_counts(self):
        for instance in self:
            instance.backup_config_count = len(instance.backup_config_ids)
            instance.backup_count = len(instance.backup_record_ids)

    def action_open_backup_configs(self):
        self.ensure_one()
        return {
            'name': _('Backup Configurations'),
            'type': 'ir.actions.act_window',
            'res_model': 'docker.backup.config',
            'view_mode': 'tree,form',
            'domain': [('instance_id', '=', self.id)],
            'context': {'default_instance_id': self.id},
        }

    def action_open_backups(self):
        self.ensure_one()
        return {
            'name': _('Backups'),
            'type': 'ir.actions.act_window',
            'res_model': 'docker.backup',
            'view_mode': 'tree,form',
            'domain': [('instance_id', '=', self.id)],
            'context': {'default_instance_id': self.id},
        }

    def action_run_backup_now(self):
        self.ensure_one()
        config = self.backup_config_ids.filtered(lambda c: c.active)[:1]
        if not config:
            raise UserError(_("No active backup configuration found."))
        return config.execute_backup(manual=True)

    def unlink(self):
        for rec in self:
            if rec.state == 'running':
                compose = os.path.join(rec.instance_path, 'docker-compose.yml')
                if os.path.exists(compose):
                    try:
                        rec._run(f"docker-compose -f {compose} down -v")
                        rec.message_post(body=_("Instance containers stopped and removed before deletion."))
                    except Exception as e:
                        _logger.warning(f"Cleanup failed for {rec.name}: {e}")
                        rec.message_post(body=_("Cleanup failed: %s") % e)
        return super().unlink()
