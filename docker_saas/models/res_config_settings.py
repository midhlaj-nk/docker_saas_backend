# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Traefik Domain Configuration
    traefik_subdomain = fields.Char(
        string='Base Domain',
        config_parameter='docker_saas.traefik_subdomain',
        default='easyinstance.com',
        help="Base domain for Traefik routing. Instances will be accessible at: instance-name.easyinstance.com"
    )
    
    # Traefik HTTPS Configuration
    traefik_enable_https = fields.Boolean(
        string='Enable HTTPS',
        config_parameter='docker_saas.traefik_enable_https',
        default=True,
        help="Enable HTTPS/TLS for Traefik mapped domains"
    )
    traefik_cert_resolver = fields.Char(
        string='Certificate Resolver',
        config_parameter='docker_saas.traefik_cert_resolver',
        default='letsencrypt',
        help="Traefik certificate resolver name for HTTPS/TLS"
    )
    traefik_http_entrypoint = fields.Char(
        string='HTTP Entrypoint',
        config_parameter='docker_saas.traefik_http_entrypoint',
        default='web',
        help="Traefik HTTP entrypoint name"
    )
    traefik_https_entrypoint = fields.Char(
        string='HTTPS Entrypoint',
        config_parameter='docker_saas.traefik_https_entrypoint',
        default='websecure',
        help="Traefik HTTPS entrypoint name"
    )

    # GitHub Configuration
    git_auth_user = fields.Char(
        string='GitHub Username',
        config_parameter='docker_saas.git_auth_user',
        help="GitHub username (or organization) used to create repositories for custom addons."
    )
    git_auth_password = fields.Char(
        string='GitHub Token',
        config_parameter='docker_saas.git_auth_password',
        help="GitHub personal access token with repo permissions."
    )
    git_webhook_url = fields.Char(
        string='GitHub Webhook URL',
        config_parameter='docker_saas.git_webhook_url',
        help="Jenkins webhook URL for GitHub push notifications (e.g., https://jenkins.example.com/github-webhook/)."
    )

    # Jenkins Configuration
    jenkins_url = fields.Char(
        string='Jenkins URL',
        config_parameter='docker_saas.jenkins_url',
        help="Jenkins server base URL (e.g., http://jenkins.example.com/)."
    )
    jenkins_username = fields.Char(
        string='Jenkins Username',
        config_parameter='docker_saas.jenkins_username',
        help="Jenkins username for API authentication."
    )
    jenkins_password = fields.Char(
        string='Jenkins Password/Token',
        config_parameter='docker_saas.jenkins_password',
        help="Jenkins password or API token."
    )

    development_mode = fields.Boolean(
        string='Development Mode',
        config_parameter='docker_saas.development_mode',
        help="Expose host ports for local debugging. Disable to rely solely on Traefik routing and avoid port conflicts."
    )

