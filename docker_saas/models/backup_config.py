# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime, timedelta

import requests
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DockerBackupConfig(models.Model):
    _name = 'docker.backup.config'
    _description = 'Docker Instance Backup Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(default='Backup Configuration', tracking=True)
    instance_id = fields.Many2one(
        'docker.instance',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    backup_frequency = fields.Selection(
        [
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily',
        required=True,
        tracking=True,
    )
    backup_destination = fields.Selection(
        [
            ('local', 'Local Storage'),
        ],
        default='local',
        required=True,
        tracking=True,
    )
    backup_directory = fields.Char(
        help='Absolute path where backup archives will be stored.',
        tracking=True,
    )
    auto_prune = fields.Boolean(
        string='Remove Old Backups',
        default=True,
        help='Automatically delete backups older than configured days.',
    )
    days_to_keep = fields.Integer(
        string='Keep Backups (days)',
        default=30,
        help='Backups older than this will be deleted automatically.',
    )
    last_execution = fields.Datetime(readonly=True, tracking=True)
    next_execution = fields.Datetime(readonly=True, tracking=True)
    last_status = fields.Selection(
        [
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        readonly=True,
        tracking=True,
    )
    last_message = fields.Text(readonly=True)
    backup_record_ids = fields.One2many(
        'docker.backup', 'config_id', string='Backups', readonly=True
    )
    backup_count = fields.Integer(compute='_compute_backup_count')

    @api.depends('backup_record_ids')
    def _compute_backup_count(self):
        for config in self:
            config.backup_count = len(config.backup_record_ids)

    @api.onchange('instance_id')
    def _onchange_instance_id(self):
        if self.instance_id and not self.backup_directory:
            path = self.instance_id.instance_path or ''
            if path:
                self.backup_directory = os.path.join(path, 'backups')

    @api.constrains('days_to_keep')
    def _check_days_to_keep(self):
        for record in self:
            if record.auto_prune and record.days_to_keep <= 0:
                raise UserError(_("Days to keep must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        updated_vals = []
        for vals in vals_list:
            vals = dict(vals)
            if not vals.get('backup_directory') and vals.get('instance_id'):
                instance = self.env['docker.instance'].browse(vals['instance_id'])
                if instance and instance.instance_path:
                    vals['backup_directory'] = os.path.join(instance.instance_path, 'backups')
            updated_vals.append(vals)
        records = super().create(updated_vals)
        for config in records:
            config._schedule_next_execution()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_schedule') and any(
            field in vals for field in ('backup_frequency', 'next_execution', 'active')
        ):
            for config in self:
                if config.active:
                    config._schedule_next_execution()
        return res

    def _schedule_next_execution(self, from_date=None):
        self.ensure_one()
        if not self.active:
            self.next_execution = False
            return

        reference = from_date or fields.Datetime.now()
        if self.backup_frequency == 'daily':
            next_dt = reference + timedelta(days=1)
        elif self.backup_frequency == 'weekly':
            next_dt = reference + timedelta(weeks=1)
        else:
            next_dt = reference + relativedelta(months=1)
        self.with_context(skip_schedule=True).write({'next_execution': next_dt})

    @api.model
    def run_scheduled_backups(self):
        now = fields.Datetime.now()
        configs = self.search(
            [
                ('active', '=', True),
                ('next_execution', '!=', False),
                ('next_execution', '<=', now),
            ]
        )
        for config in configs:
            try:
                config.execute_backup()
            except Exception as exc:
                _logger.exception("Backup failed for %s", config.instance_id.name)
                config._handle_backup_failure(str(exc))

    def execute_backup(self, manual=False):
        self.ensure_one()
        if not self.instance_id:
            raise UserError(_("No instance linked."))

        instance = self.instance_id
        if not instance.http_port:
            raise UserError(_("Instance %s has no HTTP port.") % instance.name)

        if not instance.db_name:
            raise UserError(_("No database name for %s.") % instance.name)

        backup_dir = self._ensure_backup_directory()
        now = fields.Datetime.now()
        timestamp = fields.Datetime.context_timestamp(self, now).strftime('%Y%m%d_%H%M%S')
        file_name = f"{instance.db_name}_{timestamp}.zip"
        file_path = os.path.join(backup_dir, file_name)

        url = f"http://127.0.0.1:{instance.http_port}/web/database/backup"
        payload = {
            'master_pwd': instance.admin_password or 'admin',
            'name': instance.db_name,
            'backup_format': 'zip',
        }

        _logger.info("Starting backup for %s (DB: %s)", instance.name, instance.db_name)
        try:
            response = requests.post(url, data=payload, timeout=600)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("Backup request failed: %s") % exc) from exc

        with open(file_path, 'wb') as backup_file:
            backup_file.write(response.content)

        file_size = os.path.getsize(file_path)

        backup_record = self.env['docker.backup'].create({
            'name': file_name,
            'instance_id': instance.id,
            'config_id': self.id,
            'file_path': file_path,
            'file_size': file_size,
            'backup_date': now,
            'status': 'success',
            'message': f'Stored locally at {file_path}',
        })

        self.last_execution = now
        self.last_status = 'success'
        self.last_message = f'Backup created: {file_name}'
        self._schedule_next_execution(now)

        if self.auto_prune:
            self._prune_old_backups()

        _logger.info("Backup completed: %s", file_path)
        if manual:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Backup Created'),
                    'message': _('Backup saved: %s') % file_name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        return backup_record

    def action_execute_backup(self):
        self.ensure_one()
        return self.execute_backup(manual=True)

    def _handle_backup_failure(self, message):
        self.ensure_one()
        self.last_execution = fields.Datetime.now()
        self.last_status = 'failed'
        self.last_message = message
        self._schedule_next_execution(self.last_execution)
        self.env['docker.backup'].create({
            'name': _('Failed Backup'),
            'instance_id': self.instance_id.id,
            'config_id': self.id,
            'status': 'failed',
            'message': message,
        })

    def _ensure_backup_directory(self):
        self.ensure_one()
        if not self.backup_directory:
            if not self.instance_id.instance_path:
                raise UserError(_("Instance path not configured."))
            self.backup_directory = os.path.join(self.instance_id.instance_path, 'backups')
        os.makedirs(self.backup_directory, exist_ok=True)
        return self.backup_directory

    def _prune_old_backups(self):
        self.ensure_one()
        if not self.auto_prune or self.days_to_keep <= 0:
            return

        cutoff = fields.Datetime.now() - timedelta(days=self.days_to_keep)
        old_backups = self.backup_record_ids.filtered(
            lambda rec: rec.status == 'success' and rec.backup_date and rec.backup_date < cutoff
        )
        for backup in old_backups:
            backup.unlink()


class DockerBackup(models.Model):
    _name = 'docker.backup'
    _description = 'Docker Instance Backup'
    _order = 'backup_date desc'

    name = fields.Char(required=True)
    instance_id = fields.Many2one('docker.instance', required=True, ondelete='cascade')
    config_id = fields.Many2one('docker.backup.config', ondelete='set null')
    backup_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    file_path = fields.Char()
    file_size = fields.Integer()
    readable_size = fields.Char(compute='_compute_readable_size')
    status = fields.Selection(
        [
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        default='success',
    )
    message = fields.Text()

    def _compute_readable_size(self):
        for record in self:
            record.readable_size = record._get_human_size(record.file_size)

    @staticmethod
    def _get_human_size(size):
        if not size:
            return '0 B'
        power = 1024
        n = 0
        labels = ['B', 'KB', 'MB', 'GB', 'TB']
        while size > power and n < len(labels) - 1:
            size /= power
            n += 1
        return f"{size:.2f} {labels[n]}"

    def action_download(self):
        self.ensure_one()
        if not self.file_path:
            raise UserError(_("No file path stored."))
        return {
            'type': 'ir.actions.act_url',
            'url': f"/docker_saas/backup/download/{self.id}",
            'target': 'self',
        }

    def unlink(self):
        for record in self:
            if record.file_path and os.path.exists(record.file_path):
                try:
                    os.remove(record.file_path)
                except OSError as exc:
                    _logger.warning("Unable to remove: %s - %s", record.file_path, exc)
        return super().unlink()

