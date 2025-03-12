/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";  // Assurez-vous d'importer correctement rpc

// Store the original setup method before patching
const originalSetup = KanbanController.prototype.setup;

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
        // Get the current active record (job posting)
        const activeId = 3;

        if (!activeId) {
            // Updated notification method
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
            // Utiliser rpc à la place de jsonrpc et ajouter csrf_token
            const result = await rpc("/recruitment/analyze_cvs", {
            job_id: activeId
            });

            // Display results
            if (result && result.length > 0) {
                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Résultats d\'analyse',
                    res_model: 'hr.applicant.analysis',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['id', 'in', result]],
                });
            } else {
                this.notificationService.add('Aucun CV trouvé pour cette offre d\'emploi', {
                    title: 'Information',
                    type: 'info',
                });
            }
        } catch (error) {
            // Show error
            this.notificationService.add(`Une erreur est survenue lors de l'analyse: ${error}`, {
                title: 'Erreur',
                type: 'danger',
            });
        }
    },
});
