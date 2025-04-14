import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

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
        let jobId = 0;

        // Récupérer le chemin complet de l'URL
        const pathName = window.location.pathname;
        console.log("URL path:", pathName);

        // Format attendu: /odoo/recruitment/ID/action-XXX
        const recruitmentPathRegex = /\/(?:odoo\/)?recruitment\/(\d+)/;
        const match = pathName.match(recruitmentPathRegex);

        if (match && match[1]) {
            jobId = parseInt(match[1]);
            console.log("ID extrait du chemin:", jobId);
        }

        // En cas d'échec, essayer de récupérer depuis le modèle
        if (!jobId && this.model && this.model.root) {
            jobId = this.model.root.resId;
            console.log("ID récupéré du modèle:", jobId);
        }

        // Si jobId est undefined ou vide, ajouter un mécanisme de gestion d'erreur
        if (!jobId) {
            this.notificationService.add("Impossible de déterminer l'ID de l'offre d'emploi", {
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
            // Première étape : analyse des CVs
            const analysisResult = await rpc("/recruitment/analyze_cvs", {
                job_id: jobId
            });

            console.log("Résultat de l'analyse:", analysisResult);

            if (!analysisResult.success) {
                throw new Error(analysisResult.message || 'Échec de l\'analyse des CVs');
            }

            // Deuxième étape : évaluation et calcul des scores
            const scoringResult = await rpc("/recruitment/evaluate_cvs/" + jobId, {});

            console.log("Résultat de l'évaluation des scores:", scoringResult);

            if (!scoringResult.success) {
                throw new Error(scoringResult.message || 'Échec de l\'évaluation des scores');
            }

            // Traiter et afficher les résultats des scores
            this.displayScoreResults(scoringResult.results);

            // Télécharger le fichier CSV s'il est disponible
            if (analysisResult.csv_url) {
                window.location.href = analysisResult.csv_url;
                this.notificationService.add(`Analyse terminée (${analysisResult.cv_count || 0} CVs traités), téléchargement du fichier CSV en cours...`, {
                    title: 'Succès',
                    type: 'success',
                });
            }
        } catch (error) {
            console.error("Erreur lors de l'analyse et de l'évaluation:", error);
            this.notificationService.add(`Une erreur est survenue: ${error.message}`, {
                title: 'Erreur',
                type: 'danger',
            });
        }
    },

    displayScoreResults(results) {
        // Afficher une notification avec un résumé
        const topCandidates = results.slice(0, 3);
        const summaryMessage = topCandidates.map(
            (candidate, index) => `${index + 1}. ${candidate.Nom || 'Candidat'}: ${candidate.score || 0} points`
        ).join('\n');

        this.notificationService.add(
            `Top 3 candidats:\n${summaryMessage}`,
            {
                title: 'Résultats de l\'analyse',
                type: 'success',
                sticky: true
            }
        );
    }
});
