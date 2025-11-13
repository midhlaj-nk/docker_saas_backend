/* @odoo-module */

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { loadCSS, loadJS } from "@web/core/assets";
import { jsonrpc } from "@web/core/network/rpc_service";

export class AddCustomModuleWidget extends Component {
    setup() {
        this.fileInput = useRef("file");
        this.state = useState({
            fileList: [],
            loading: false,
            error: null,
            uploadProgress: 0,
            isUploading: false,
        });

        this.addonsPath = this.computeAddonsPath(this.props);
        this.instanceName = this.props.record?.data?.name || "";
        this.assetsLoaded = false;
        this.pond = null;

        this.deleteFile = this.deleteFile.bind(this);
        this.handleHelpSwal = this.handleHelpSwal.bind(this);

        onWillStart(async () => {
            if (!this.canInteract) {
                return;
            }
            await this.loadAssets();
            await this.fetchFiles();
        });

        onMounted(() => {
            if (this.canInteract) {
                this.initFilePond();
            }
        });

        onWillUnmount(() => this.destroyFilePond());

        onWillUpdateProps(async (nextProps) => {
            const previousAddonsPath = this.addonsPath;
            const previousInstanceName = this.instanceName;
            const wasInteractive = this.canInteract;

            const nextAddonsPath = this.computeAddonsPath(nextProps);
            const nextInstanceName = nextProps.record?.data?.name || "";

            this.addonsPath = nextAddonsPath;
            this.instanceName = nextInstanceName;

            if (!this.canInteract) {
                if (wasInteractive) {
                    this.destroyFilePond();
                    this.state.fileList = [];
                }
                return;
            }

            if (!this.assetsLoaded) {
                await this.loadAssets();
            }

            const pathChanged = previousAddonsPath !== nextAddonsPath;
            const instanceChanged = previousInstanceName !== nextInstanceName;

            if (pathChanged || instanceChanged) {
                await this.fetchFiles();
                this.resetFilePond();
            }
        });
    }

    get canInteract() {
        return Boolean(this.addonsPath && this.instanceName);
    }

    get isReadonly() {
        return Boolean(this.props.readonly);
    }

    computeAddonsPath(props) {
        const basePath = props?.record?.data?.instance_path;
        if (!basePath) {
            return "";
        }
        const sanitizedBase = basePath.replace(/\/$/, "");
        return `${sanitizedBase}/addons`;
    }

    async loadAssets() {
        if (this.assetsLoaded) {
            return;
        }
        await loadJS("docker_saas/static/src/libs/filepond/filepond.js");
        await loadJS("docker_saas/static/src/libs/filepond/filepond-plugin-file-validate-type.js");
        await loadCSS("docker_saas/static/src/libs/filepond/filepond.css");
        try {
            await loadJS("https://cdn.jsdelivr.net/npm/sweetalert2@11");
        } catch (error) {
            console.warn("SweetAlert could not be loaded:", error);
        }
        if (window.FilePond && window.FilePondPluginFileValidateType) {
            window.FilePond.registerPlugin(window.FilePondPluginFileValidateType);
        }
        this.assetsLoaded = true;
    }

    async fetchFiles() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const { files = [] } = await jsonrpc("/docker_saas/files/list", {
                addons_path: this.addonsPath,
            });
            this.state.fileList = files;
        } catch (error) {
            console.error("Unable to retrieve module list:", error);
            this.state.error =
                (this.env._t && this.env._t("Unable to retrieve module list.")) ||
                "Unable to retrieve module list.";
            this.state.fileList = [];
        } finally {
            this.state.loading = false;
        }
    }

    initFilePond() {
        this.destroyFilePond();
        if (!window.FilePond || !this.fileInput.el) {
            return;
        }

        const uploadUrl = `/docker_saas/file/upload/${encodeURIComponent(this.addonsPath)}/${encodeURIComponent(this.instanceName)}`;

        this.pond = window.FilePond.create(this.fileInput.el, {
            allowRevert: false,
            acceptedFileTypes: ["application/zip"],
            labelIdle: 'Drag & Drop your ZIP module or <span class="filepond--label-action">Browse</span>',
            fileValidateTypeDetectType: (source) =>
                new Promise((resolve, reject) => {
                    const name = (source && (source.name || source.webkitRelativePath || "")) || "";
                    if (name.toLowerCase().endsWith(".zip")) {
                        resolve("application/zip");
                    } else {
                        reject("Invalid file type");
                    }
                }),
            server: {
                process: {
                    url: uploadUrl,
                    headers: {
                        "X-CSRFToken": odoo.csrf_token,
                    },
                    onload: (response) => {
                        this.state.isUploading = false;
                        this.state.uploadProgress = 0;
                        this.fetchFiles();
                        // Show success message
                        if (window.Swal) {
                            window.Swal.fire({
                                icon: "success",
                                title: "Upload Successful!",
                                text: "Module uploaded and extracted successfully. Instance is restarting...",
                                timer: 3000,
                                showConfirmButton: false,
                            });
                        }
                    },
                    onerror: (error) => {
                        console.error("File upload error:", error);
                        this.state.isUploading = false;
                        this.state.uploadProgress = 0;
                        this.state.error = "Upload failed. Please try again.";
                        // Show error message
                        if (window.Swal) {
                            window.Swal.fire({
                                icon: "error",
                                title: "Upload Failed",
                                text: error.toString() || "An error occurred during upload.",
                            });
                        }
                    },
                    ondata: (formData) => {
                        this.state.isUploading = true;
                        return formData;
                    },
                },
            },
        });

        this.pond.on("addfilestart", () => {
            this.state.isUploading = true;
            this.state.uploadProgress = 0;
        });

        this.pond.on("addfileprogress", (file, progress) => {
            this.state.uploadProgress = Math.round(progress * 100);
        });

        this.pond.on("processfile", (error, file) => {
            if (!error && this.pond) {
                setTimeout(() => {
                    if (this.pond) {
                        this.pond.removeFile(file.id);
                    }
                }, 5000);
            }
        });

        this.pond.on("warning", (error, file) => {
            console.warn("FilePond warning:", error, file);
        });
    }

    resetFilePond() {
        if (this.canInteract) {
            this.initFilePond();
        } else {
            this.destroyFilePond();
        }
    }

    destroyFilePond() {
        if (this.pond) {
            this.pond.destroy();
            this.pond = null;
        }
    }

    async deleteFile(fileName) {
        if (!fileName) {
            return;
        }

        // Confirm deletion with SweetAlert
        if (window.Swal) {
            const result = await window.Swal.fire({
                title: "Delete Module?",
                text: `Are you sure you want to delete "${fileName}"? This action cannot be undone.`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonColor: "#d33",
                cancelButtonColor: "#3085d6",
                confirmButtonText: "Yes, delete it!",
                cancelButtonText: "Cancel",
            });

            if (!result.isConfirmed) {
                return;
            }
        } else {
            // Fallback to native confirm
            if (!window.confirm(`Are you sure you want to delete "${fileName}"?`)) {
                return;
            }
        }

        this.state.loading = true;
        try {
            const response = await jsonrpc("/docker_saas/file/delete", {
                addons_path: this.addonsPath,
                fileName,
                instance: this.instanceName,
            });
            
            if (response?.status === "success") {
                await this.fetchFiles();
                // Show success message
                if (window.Swal) {
                    window.Swal.fire({
                        icon: "success",
                        title: "Deleted!",
                        text: `"${fileName}" has been deleted. Instance is restarting...`,
                        timer: 3000,
                        showConfirmButton: false,
                    });
                }
            } else {
                throw new Error(response?.message || "Delete failed");
            }
        } catch (error) {
            console.error("Error deleting module:", error);
            this.state.error = `Failed to delete "${fileName}". Please try again.`;
            // Show error message
            if (window.Swal) {
                window.Swal.fire({
                    icon: "error",
                    title: "Delete Failed",
                    text: error.toString() || "An error occurred during deletion.",
                });
            }
        } finally {
            this.state.loading = false;
        }
    }

    handleHelpSwal() {
        if (window.Swal) {
            window.Swal.fire({
                title: "<h3 style='font-weight: bold; color: #4CAF50;'>How to Upload an Odoo Module to Your Docker Instance</h3>",
                html: `
                    <div style="text-align: left; font-size: 16px; line-height: 1.6;">
                        <ol style="padding-left: 20px;">
                            <li style="margin-bottom: 15px;">
                                <strong style="color: #333;">Step 1:</strong> Download the module from 
                                <a href="https://apps.odoo.com/apps" target="_blank" style="color: #2196F3; text-decoration: underline;">Odoo Apps Store</a> 
                                or prepare your custom module as a ZIP file.
                            </li>
                            <li style="margin-bottom: 15px;">
                                <strong style="color: #333;">Step 2:</strong> 
                                Ensure the ZIP file contains the module folder (e.g., <code>my_module/</code>) with <code>__manifest__.py</code> inside.
                            </li>
                            <li style="margin-bottom: 15px;">
                                <strong style="color: #333;">Step 3:</strong> 
                                Drag the module ZIP file into the upload area below, or click "Browse" to select it. Modules are unpacked directly inside your instance's <code>addons/</code> folder.
                            </li>
                            <li style="margin-bottom: 15px;">
                                <strong style="color: #333;">Step 4:</strong> 
                                Wait for the upload to complete. The module will be automatically extracted and your Docker instance will restart.
                            </li>
                            <li>
                                <strong style="color: #333;">Step 5:</strong> 
                                After restart, go to <strong>Apps</strong> → <strong>Update Apps List</strong>, then search for and install your module.
                            </li>
                        </ol>
                        <div style="margin-top: 20px; padding: 10px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                            <strong>⚠️ Note:</strong> Only ZIP files are accepted. They are extracted into <code>addons/</code>, and the instance restarts automatically after upload or delete.
                        </div>
                    </div>
                `,
                icon: "info",
                background: "#f9f9f9",
                confirmButtonText: "<span style='font-size: 16px;'>Got it!</span>",
                confirmButtonColor: "#4CAF50",
                width: "650px",
            });
        } else {
            window.alert("Download a module ZIP from Odoo Apps and upload it using the input below. The instance will restart automatically.");
        }
    }
}

AddCustomModuleWidget.template = "docker_saas.AddCustomModuleWidget";

export const addCustomModuleWidget = {
    component: AddCustomModuleWidget,
};

registry.category("view_widgets").add("add_custom_module_widget", addCustomModuleWidget);

