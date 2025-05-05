import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// Stocke la méthode setup originale avant de la patcher
const originalSetup = KanbanController.prototype.setup;

patch(KanbanController.prototype, {
    setup() {
        // Appelle la méthode setup originale
        originalSetup.call(this);

        // Ajoute la configuration personnalisée
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },

    // Redirection vers le tableau de bord recrutement
    redirectToDashboard() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Tableau de bord recrutement',
            res_model: 'hr.recruitment.dashboard',
            views: [[false, 'form']],
            target: 'new',
        });
    },

    // Exécution de l'analyse IA
    async runAIAnalysis() {
        let jobId = 0;

        // Récupère le chemin complet de l'URL
        const pathName = window.location.pathname;
        console.log("URL path:", pathName);

        // Format attendu : /odoo/recruitment/ID/action-XXX
        const recruitmentPathRegex = /\/(?:odoo\/)?recruitment\/(\d+)/;
        const match = pathName.match(recruitmentPathRegex);

        if (match && match[1]) {
            jobId = parseInt(match[1]);
            console.log("ID extrait du chemin:", jobId);
        }

        // En cas d'échec, essaie de récupérer depuis le modèle
        if (!jobId && this.model && this.model.root) {
            jobId = this.model.root.resId;
            console.log("ID récupéré du modèle:", jobId);
        }

        // Si jobId est vide, gestion de l'erreur
        if (!jobId) {
            this.notificationService.add("Impossible de déterminer l'ID de l'offre d'emploi", {
                title: 'Erreur',
                type: 'danger',
            });
            return;
        }

        // Affiche une notification de traitement
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

            // Deuxième étape : évaluation des scores
            const scoringResult = await rpc(`/recruitment/evaluate_cvs/${jobId}`, {});

            console.log("Résultat de l'évaluation des scores:", scoringResult);

            if (!scoringResult.success) {
                throw new Error(scoringResult.message || 'Échec de l\'évaluation des scores');
            }

            // Affiche les résultats des scores
            this.displayScoreResults(scoringResult.results);

            // Télécharge le fichier CSV si disponible
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

    // Affichage des résultats des scores
    displayScoreResults(results) {
        // Vérifie que 'results' est un tableau valide et qu'il contient des éléments
        if (Array.isArray(results) && results.length > 0) {
            // Trier les résultats par score décroissant
            results.sort((a, b) => b.score - a.score);

            // Limite à 3 premiers candidats
            const topCandidates = results.slice(0, 3);

            const summaryMessage = topCandidates.map(
                (candidate, index) => `${index + 1}. ${candidate.Nom || 'Candidat'}: ${candidate.score || 0} points`
            ).join('\n');

            // Affiche une notification avec les 3 premiers candidats
            this.notificationService.add(
                `Top 3 candidats:\n${summaryMessage}`,
                {
                    title: 'Résultats de l\'analyse',
                    type: 'success',
                    sticky: true
                }
            );
        } else {
            // Vérification et log si les résultats sont invalides ou vides
            console.error('Erreur: les résultats de l\'évaluation sont invalides ou vides', results);
            this.notificationService.add('Aucun candidat valide trouvé', {
                title: 'Erreur',
                type: 'danger',
            });
        }
    }
});
