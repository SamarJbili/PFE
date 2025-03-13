/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// Store the original setup method before patching
const originalSetup = KanbanController.prototype.setup;

// Mode test - mettre à true pour les tests, false en production
const TEST_MODE = true;
const TEST_JOB_ID = 2; // ID de test pour développement

patch(KanbanController.prototype, {
    setup() {
        // Call the original setup method
        originalSetup.call(this);

        // Add your custom setup
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },

    redirectToDashboard() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Tableau de bord recrutement',
            res_model: 'hr.recruitment.dashboard',
            views: [[false, 'form']],
            target: 'new',
        });
    },

    async runAIAnalysis() {
        // En mode test, utilisez l'ID de test; sinon, obtenez l'ID sélectionné
        let activeId = TEST_MODE ? TEST_JOB_ID : (this.model && this.model.root ? this.model.root.resId : null);

        console.log("ID du poste utilisé:", activeId);

        if (!activeId) {
            this.notificationService.add('Veuillez sélectionner une offre d\'emploi', {
                title: 'Erreur',
                type: 'danger',
            });
            return;
        }

        // Show a simple notification for loading
        this.notificationService.add('Traitement des CVs en cours...', {
            title: 'Analyse en cours',
            type: 'info',
        });

        try {
            const result = await rpc("/recruitment/analyze_cvs", {
                job_id: activeId
            });

            console.log("Résultat de l'analyse:", result);

            // Handle the response based on the actual backend structure
            if (result.success) {
                if (result.csv_url) {
                    // If successful and has a CSV URL, download or redirect to it
                    window.location.href = result.csv_url;
                    this.notificationService.add(`Analyse terminée (${result.cv_count || 0} CVs traités), téléchargement du fichier CSV en cours...`, {
                        title: 'Succès',
                        type: 'success',
                    });
                } else {
                    this.notificationService.add('Analyse terminée mais aucun lien CSV généré', {
                        title: 'Avertissement',
                        type: 'warning',
                    });
                }
            } else {
                // Show the error message from the backend
                this.notificationService.add(result.message || 'Une erreur inconnue est survenue', {
                    title: 'Information',
                    type: 'info',
                });
            }
        } catch (error) {
            console.error("Erreur lors de l'analyse:", error);
            // Show error
            this.notificationService.add(`Une erreur est survenue lors de l'analyse: ${error}`, {
                title: 'Erreur',
                type: 'danger',
            });
        }
    },
});