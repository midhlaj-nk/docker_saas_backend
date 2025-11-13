# -*- coding: utf-8 -*-
import os

from odoo import http
from odoo.http import request, content_disposition


class BackupDownloadController(http.Controller):

    @http.route('/docker_saas/backup/download/<int:backup_id>', type='http', auth='user')
    def download_backup(self, backup_id, **kwargs):
        backup = request.env['docker.backup'].browse(backup_id).sudo()
        if not backup.exists():
            return request.not_found()

        if not backup.file_path or not os.path.exists(backup.file_path):
            return request.not_found()

        file_name = backup.name or os.path.basename(backup.file_path)
        with open(backup.file_path, 'rb') as backup_file:
            file_content = backup_file.read()
        
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', content_disposition(file_name)),
        ]
        return request.make_response(file_content, headers=headers)

