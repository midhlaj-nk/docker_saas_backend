# -*- coding: utf-8 -*-
import logging
import os
import shutil
import zipfile
from urllib.parse import unquote

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DockerSaasModuleController(http.Controller):

    def _get_instance_by_name(self, name):
        instance = request.env['docker.instance'].sudo().search([('name', '=', name)], limit=1)
        if not instance:
            raise NotFound("Instance not found")
        return instance

    def _ensure_path(self, path):
        normalized = os.path.abspath(path)
        os.makedirs(normalized, exist_ok=True)
        return normalized

    @http.route('/docker_saas/files/list', type='json', auth='user')
    def list_files(self, **kwargs):
        addons_path = kwargs.get('addons_path')
        if not addons_path:
            _logger.debug("list_files called without addons_path")
            return {'files': []}
        addons_path = self._ensure_path(addons_path)
        _logger.info("Listing custom modules in %s", addons_path)
        entries = []
        if os.path.exists(addons_path):
            for entry in sorted(os.listdir(addons_path)):
                if entry.startswith('.'):
                    continue
                full_path = os.path.join(addons_path, entry)
                if os.path.isdir(full_path):
                    entries.append(entry)
                    _logger.debug("Found module directory: %s", entry)
        else:
            _logger.warning("Custom addons path does not exist: %s", addons_path)
        return {'files': entries}

    @http.route('/docker_saas/file/upload/<path:pvc_path>/<string:instance>', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_file(self, pvc_path, instance, **kwargs):
        pvc_path = self._ensure_path(unquote(pvc_path))
        _logger.info("Received upload request for instance '%s' into path %s", instance, pvc_path)
        
        # Handle both old-style and new-style file uploads
        uploaded_file = None
        if 'filepond' in request.httprequest.files:
            uploaded_file = request.httprequest.files['filepond']
        elif 'file' in request.httprequest.files:
            uploaded_file = request.httprequest.files['file']
        
        if not uploaded_file:
            _logger.error("Upload failed: no file provided")
            return http.Response("No file uploaded", status=400)

        filename = os.path.basename(uploaded_file.filename)
        if not filename.endswith('.zip'):
            _logger.error("Upload failed: non-zip file '%s'", filename)
            return http.Response("Only ZIP archives are supported", status=400)

        target_zip = os.path.join(pvc_path, filename)
        _logger.debug("Saving uploaded file to %s", target_zip)
        with open(target_zip, 'wb') as destination:
            destination.write(uploaded_file.read())

        try:
            with zipfile.ZipFile(target_zip, 'r') as archive:
                _logger.info("Extracting ZIP '%s' into %s", filename, pvc_path)
                archive.extractall(pvc_path)
        except zipfile.BadZipFile:
            _logger.exception("Bad ZIP archive uploaded: %s", filename)
            os.remove(target_zip)
            return http.Response("Invalid ZIP archive", status=400)
        finally:
            if os.path.exists(target_zip):
                _logger.debug("Removing temporary ZIP %s", target_zip)
                os.remove(target_zip)

        instance_rec = self._get_instance_by_name(instance)
        _logger.info("Restarting instance '%s' after module upload", instance)
        instance_rec.action_restart_instance()

        return http.Response("File processed successfully")

    @http.route('/docker_saas/file/delete', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_file(self, **kwargs):
        addons_path = kwargs.get('addons_path')
        file_name = kwargs.get('fileName')
        instance = kwargs.get('instance')

        if not addons_path or not file_name:
            _logger.error("Delete request missing parameters: addons_path=%s fileName=%s", addons_path, file_name)
            return {'status': 'error', 'message': 'Missing parameters'}

        addons_path = self._ensure_path(addons_path)
        target = os.path.join(addons_path, file_name)
        _logger.info("Deleting custom module '%s' from %s", file_name, addons_path)

        if not os.path.exists(target):
            _logger.warning("Delete failed: target does not exist %s", target)
            return {'status': 'error', 'message': 'File not found'}

        if os.path.isdir(target):
            _logger.debug("Removing directory %s", target)
            shutil.rmtree(target)
        else:
            _logger.debug("Removing file %s", target)
            os.remove(target)

        if instance:
            _logger.info("Restarting instance '%s' after deleting module '%s'", instance, file_name)
            self._get_instance_by_name(instance).action_restart_instance()

        return {'status': 'success'}

