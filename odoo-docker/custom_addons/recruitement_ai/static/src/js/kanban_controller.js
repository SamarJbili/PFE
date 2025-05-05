import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// Stocker la méthode setup originale
const originalSetup = KanbanController.prototype.setup;

patch(KanbanController.prototype, {
    setup() {
        originalSetup.call(this);
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },

    async runAIAnalysis() {
        try {
            // Initialisation des variables
            let jobId = 0;

            // Vérification du champ Rang
            const rangInput = document.getElementById('Rang');
            if (!rangInput) {
                this.notificationService.add("Champ 'Rang' introuvable dans l'interface.", {
                    title: 'Erreur',
                    type: 'danger',
                });
                return;
            }

            const rang = parseInt(rangInput.value, 10);
            if (isNaN(rang) || rang <= 0) {
                this.notificationService.add("Veuillez entrer un nombre valide supérieur à zéro dans le champ 'Rang'.", {
                    title: 'Erreur',
                    type: 'danger',
                });
                return;
            }

            // Détermination de l'ID du job
            jobId = await this.determineJobId();
            if (!jobId) {
                this.notificationService.add("Impossible de déterminer l'ID de l'offre d'emploi", {
                    title: 'Erreur',
                    type: 'danger',
                });
                return;
            }

            console.log("ID du job pour l'analyse:", jobId);

            // Notification de démarrage
            this.notificationService.add('Traitement des CVs en cours...', {
                title: 'Analyse en cours',
                type: 'info',
            });

            // Première étape : analyse des CVs
            console.log("Démarrage de l'analyse des CVs pour le job", jobId);
            const analysisResult = await rpc("/recruitment/analyze_cvs", {
                job_id: jobId,
            });

            console.log("Résultat de l'analyse des CVs:", analysisResult);
            if (!analysisResult || !analysisResult.success) {
                throw new Error(analysisResult?.message || 'Échec de l\'analyse des CVs');
            }

            // Deuxième étape : évaluation des scores
            console.log("Démarrage de l'évaluation des scores pour le job", jobId);
            const scoringResult = await rpc("/recruitment/evaluate_cvs/" + jobId, {});

            console.log("Résultat de l'évaluation des scores:", scoringResult);
            if (!scoringResult || !scoringResult.success) {
                throw new Error(scoringResult?.message || 'Échec de l\'évaluation des scores');
            }

            // Récupération des candidats évalués
            let candidatesData = [];
            if (scoringResult.results) {
                candidatesData = scoringResult.results;
                console.log("Candidats trouvés dans 'results':", candidatesData.length);
            } else if (scoringResult.evaluated_candidates) {
                candidatesData = scoringResult.evaluated_candidates;
                console.log("Candidats trouvés dans 'evaluated_candidates':", candidatesData.length);
            } else if (scoringResult.candidates) {
                candidatesData = scoringResult.candidates;
                console.log("Candidats trouvés dans 'candidates':", candidatesData.length);
            } else {
                console.log("Structure complète du résultat:", JSON.stringify(scoringResult));
            }

            if (!Array.isArray(candidatesData) || candidatesData.length === 0) {
                throw new Error("Les résultats de l'évaluation sont absents ou invalides.");
            }

            // Debug: affichage de la structure des données des candidats
            console.log("Structure d'un candidat:", candidatesData[0]);

            // Tri des candidats par score (du plus élevé au plus faible)
            const getScore = (candidate) => {
                if (candidate.score !== undefined) return candidate.score;
                if (candidate.Score !== undefined) return candidate.Score;
                if (candidate.points !== undefined) return candidate.points;
                if (candidate.total_score !== undefined) return candidate.total_score;
                return 0; // Valeur par défaut
            };

            const sortedResults = [...candidatesData].sort((a, b) => getScore(b) - getScore(a));
            console.log("Candidats triés par score:", sortedResults);

            // Affiche tous les candidats triés
            this.displayScoreResults(sortedResults);

            // Sélectionne les N premiers candidats selon le rang spécifié
            const topCandidates = sortedResults.slice(0, rang);
            const remainingCandidates = sortedResults.slice(rang);

            console.log(`Top ${rang} candidats:`, topCandidates);
            console.log("Candidats restants:", remainingCandidates);

            // Traiter séquentiellement au lieu de parallèlement pour débogage
            if (topCandidates.length > 0) {
                await this.moveTopCandidatesToQualification(topCandidates);
            }

            if (remainingCandidates.length > 0) {
                await this.ensureRemainingCandidatesInNewStage(remainingCandidates);
            }

            // Télécharge le fichier CSV si disponible
            if (analysisResult.csv_url) {
                window.location.href = analysisResult.csv_url;
                this.notificationService.add(`Analyse terminée (${analysisResult.cv_count || 0} CVs traités), téléchargement du fichier CSV en cours...`, {
                    title: 'Succès',
                    type: 'success',
                });
            } else {
                this.notificationService.add(`Analyse terminée (${analysisResult.cv_count || 0} CVs traités)`, {
                    title: 'Succès',
                    type: 'success',
                });
            }

            // Rafraîchit la vue pour afficher les changements
            await this.model.load();

        } catch (error) {
            console.error("Erreur lors de l'analyse et de l'évaluation:", error);
            this.notificationService.add(`Une erreur est survenue: ${error.message || 'Erreur inconnue'}`, {
                title: 'Erreur',
                type: 'danger',
            });
        }
    },

    /**
 * Détermine l'ID du job à partir de différentes sources
 * @returns {Promise<number>} L'ID du job ou 0 si non trouvé
 */
async determineJobId() {
    let jobId = 0;

    // Ajout d'un log pour identifier le début de la fonction
    console.log("Début de la détermination de l'ID du job");

    // 1. Récupération depuis l'URL avec un pattern plus flexible
    const pathName = window.location.pathname;
    const searchParams = new URLSearchParams(window.location.search);

    console.log("Chemin URL:", pathName);
    console.log("Paramètres URL:", searchParams.toString());

    // 1.1 Recherche dans le chemin
    const recruitmentPathRegex = /\/(?:odoo\/)?recruitment\/(\d+)|hr_applicant_view_kanban.*model=hr.applicant.*job_id=(\d+)/;
    const pathMatch = pathName.match(recruitmentPathRegex);

    if (pathMatch && (pathMatch[1] || pathMatch[2])) {
        jobId = parseInt(pathMatch[1] || pathMatch[2], 10);
        console.log("ID extrait du chemin URL:", jobId);
        return jobId;
    }

    // 1.2 Recherche dans les paramètres d'URL
    const jobIdParam = searchParams.get('job_id');
    if (jobIdParam) {
        jobId = parseInt(jobIdParam, 10);
        if (!isNaN(jobId)) {
            console.log("ID extrait des paramètres URL:", jobId);
            return jobId;
        }
    }

    // 2. Récupération depuis le modèle avec vérification plus robuste
    if (this.model) {
        console.log("Structure du modèle:", JSON.stringify({
            hasRoot: !!this.model.root,
            resId: this.model.root?.resId
        }));

        if (this.model.root && this.model.root.resId) {
            jobId = this.model.root.resId;
            console.log("ID récupéré du modèle:", jobId);
            return jobId;
        }
    }

    // 3. Récupération depuis le contexte avec debug
    if (this.env?.searchModel?.context) {
        console.log("Contexte disponible:", Object.keys(this.env.searchModel.context));

        jobId = this.env.searchModel.context.default_job_id ||
               this.env.searchModel.context.job_id;

        if (jobId) {
            console.log("ID récupéré du contexte:", jobId);
            return jobId;
        }
    }

    // 4. Récupération depuis l'API avec gestion d'erreur améliorée
    try {
        console.log("Tentative de récupération du job actif via l'API");
        const activeJob = await rpc("/recruitment/get_active_job", {});

        console.log("Réponse de l'API get_active_job:", activeJob);

        if (activeJob && activeJob.id) {
            jobId = activeJob.id;
            console.log("ID récupéré du job actif:", jobId);
            return jobId;
        }
    } catch (error) {
        console.error("Erreur lors de la récupération du job actif:", error);
    }

    // 5. Dernière tentative avec l'élément Rang
    try {
        const rangElement = document.getElementById('Rang');
        if (rangElement && rangElement.dataset && rangElement.dataset.jobId) {
            jobId = parseInt(rangElement.dataset.jobId, 10);
            if (!isNaN(jobId)) {
                console.log("ID récupéré de l'élément Rang:", jobId);
                return jobId;
            }
        }
    } catch (error) {
        console.error("Erreur lors de la récupération de l'ID depuis l'élément Rang:", error);
    }

    console.log("Aucun ID de job trouvé, retourne 0");
    return 0; // Aucun ID trouvé
},

   /**
 * Déplace les meilleurs candidats vers l'étape "Qualification initiale"
 * @param {Array} topCandidates Liste des meilleurs candidats
 * @returns {Promise<void>}
 */
async moveTopCandidatesToQualification(topCandidates) {
    try {
        if (!topCandidates || topCandidates.length === 0) {
            console.log("Aucun candidat top à traiter");
            return;
        }

        console.log("Candidats top à déplacer:", topCandidates);

        // Recherche de l'étape "Qualification initiale"
        const stageResult = await rpc("/recruitment/get_stage_by_name", {
            name: 'Qualification initiale'
        });

        if (!stageResult?.success || !stageResult?.stage_id) {
            throw new Error("Impossible de trouver la phase 'Qualification initiale'");
        }

        const stageId = stageResult.stage_id;
        console.log("ID de l'étape 'Qualification initiale':", stageId);

        console.log("Recherche des IDs des candidats à partir de leurs noms");

        // Rechercher les candidats par nom uniquement
        const candidatesWithIds = await Promise.all(topCandidates.map(async candidate => {
            const candidateName = candidate.Nom || candidate.name;

            if (!candidateName) {
                console.warn("Candidat sans nom:", candidate);
                return null;
            }

            try {
                // Appel pour récupérer l'ID du candidat par nom
                const result = await rpc("/recruitment/get_applicant_by_name", {
                    name: candidateName  // Passer le nom original sans normalisation
                });

                if (result?.success && result?.applicant_id) {
                    console.log(`ID trouvé pour ${candidateName}: ${result.applicant_id} (score: ${result.match_score}%)`);
                    return {
                        id: result.applicant_id,
                        name: candidateName
                    };
                } else {
                    console.warn(`Aucun ID trouvé pour le nom ${candidateName}: ${result?.message || 'Raison inconnue'}`);
                    return null;
                }
            } catch (err) {
                console.error(`Erreur lors de la recherche de l'ID pour ${candidateName}:`, err);
                return null;
            }
        }));

        // Filtrer les résultats nuls
        const validCandidates = candidatesWithIds.filter(Boolean);

        if (validCandidates.length === 0) {
            throw new Error("Impossible de trouver les identifiants des candidats dans le système");
        }

        console.log("Candidats avec IDs valides:", validCandidates);

        const updatedApplicants = validCandidates.map(candidate => ({
            id: candidate.id,
            stage_id: stageId
        }));

        // Ajouter des logs pour déboguer
        console.log("Données envoyées à l'API:", {
            applicants: updatedApplicants
        });

        const updateResult = await rpc("/recruitment/update_applicants_stage", {
            applicants: updatedApplicants,
        });

        console.log("Résultat de la mise à jour:", updateResult);

        if (updateResult?.success) {
            const count = updateResult.updated_count !== undefined ?
                        updateResult.updated_count : updatedApplicants.length;
            this.notificationService.add(`${count} meilleurs CVs ont été déplacés vers la phase 'Qualification initiale'.`, {
                title: 'Succès',
                type: 'success',
            });
        } else {
            console.error("Résultat de la mise à jour des candidats:", updateResult);
            throw new Error(updateResult?.message || "Échec de la mise à jour des candidats");
        }
    } catch (error) {
        console.error("Erreur lors de la mise à jour des meilleurs CVs:", error);
        this.notificationService.add(`Impossible de déplacer les meilleurs CVs: ${error.message || 'Erreur inconnue'}`, {
            title: 'Erreur',
            type: 'danger',
        });
    }
},
    /**
 * S'assure que les candidats restants sont dans l'étape "Nouveau"
 * @param {Array} remainingCandidates Liste des candidats restants
 * @returns {Promise<void>}
 */
async ensureRemainingCandidatesInNewStage(remainingCandidates) {
    try {
        if (!remainingCandidates || remainingCandidates.length === 0) {
            console.log("Aucun candidat restant à traiter");
            return;
        }

        console.log("Candidats restants à déplacer:", remainingCandidates);

        // Recherche de l'étape "Nouveau"
        const stageResult = await rpc("/recruitment/get_stage_by_name", {
            name: 'Nouveau'
        });

        if (!stageResult?.success || !stageResult?.stage_id) {
            console.log("Phase 'Nouveau' non trouvée, les candidats restants ne seront pas modifiés");
            return;
        }

        const stageId = stageResult.stage_id;
        console.log("ID de l'étape 'Nouveau':", stageId);

        // Méthode similaire à celle utilisée dans moveTopCandidatesToQualification
        console.log("Recherche des IDs des candidats restants à partir de leurs noms");

        // Rechercher les candidats par nom (prioritaire)
        const candidatesWithIds = await Promise.all(remainingCandidates.map(async candidate => {
            const candidateName = candidate.Nom || candidate.name;

            if (!candidateName) {
                console.warn("Candidat sans nom:", candidate);
                return null;
            }

            try {
                // Appel pour récupérer l'ID du candidat par nom
                const result = await rpc("/recruitment/get_applicant_by_name", {
                    name: candidateName  // Passer le nom sans normalisation
                });

                if (result?.success && result?.applicant_id) {
                    console.log(`ID trouvé pour ${candidateName}: ${result.applicant_id} (score: ${result.match_score}%)`);
                    return {
                        id: result.applicant_id,
                        name: candidateName
                    };
                } else {
                    console.warn(`Aucun ID trouvé pour le nom ${candidateName}: ${result?.message || 'Raison inconnue'}`);

                    // Tentative de recherche par email en dernier recours
                    if (candidate.email) {
                        try {
                            const emailResult = await rpc("/recruitment/get_applicant_by_email", {
                                email: candidate.email
                            });

                            if (emailResult?.success && emailResult?.applicant_id) {
                                console.log(`ID trouvé pour ${candidate.email}: ${emailResult.applicant_id}`);
                                return {
                                    id: emailResult.applicant_id,
                                    email: candidate.email
                                };
                            }
                        } catch (err) {
                            console.error(`Erreur lors de la recherche par email pour ${candidate.email}:`, err);
                        }
                    }

                    return null;
                }
            } catch (err) {
                console.error(`Erreur lors de la recherche de l'ID pour ${candidateName}:`, err);
                return null;
            }
        }));

        // Filtrer les résultats nuls
        const validCandidates = candidatesWithIds.filter(Boolean);

        if (validCandidates.length === 0) {
            console.warn("Aucun candidat restant avec ID valide trouvé");
            return;
        }

        console.log("Candidats restants avec IDs valides:", validCandidates);

        const updatedApplicants = validCandidates.map(candidate => ({
            id: candidate.id,
            stage_id: stageId
        }));

        // Ajouter des logs pour déboguer
        console.log("Données envoyées à l'API pour les candidats restants:", {
            applicants: updatedApplicants
        });

        const updateResult = await rpc("/recruitment/update_applicants_stage", {
            applicants: updatedApplicants,
        });

        console.log("Résultat de la mise à jour des candidats restants:", updateResult);

        if (updateResult?.success) {
            const count = updateResult.updated_count !== undefined ?
                        updateResult.updated_count : updatedApplicants.length;
            console.log(`${count} candidats restants placés/maintenus dans la phase 'Nouveau'`);
            this.notificationService.add(`${count} candidats restants ont été placés dans la phase 'Nouveau'.`, {
                title: 'Information',
                type: 'info',
            });
        } else {
            console.error("Échec de la mise à jour des candidats restants:", updateResult?.message);
        }
    } catch (error) {
        console.error("Erreur lors de la gestion des candidats restants:", error);
        this.notificationService.add(`Problème lors du traitement des candidats restants: ${error.message || 'Erreur inconnue'}`, {
            title: 'Avertissement',
            type: 'warning',
        });
    }
},
    /**
     * Affiche les résultats des scores de tous les candidats
     * @param {Array} results Liste des candidats avec leurs scores
     */
    displayScoreResults(results) {
        try {
            // Vérifie que 'results' est un tableau valide
            if (!Array.isArray(results) || results.length === 0) {
                throw new Error('Les résultats sont invalides ou vides');
            }

            const summaryMessage = results.map((candidate, index) => {
                // Vérification robuste des propriétés
                if (!candidate) return `${index + 1}. Candidat invalide`;

                // Gestion de différents formats de noms
                const candidateName = candidate.name || candidate.Nom ||
                                    candidate.partner_name || 'Candidat sans nom';

                // Vérification du score
                const score = typeof candidate.score === 'number' ?
                            candidate.score.toFixed(2) : // Limité à 2 décimales
                            (candidate.score || 0);

                return `${index + 1}. ${candidateName}: ${score} points`;
            }).join('\n');

            // Affiche une notification avec tous les candidats triés
            this.notificationService.add(
                `Candidats triés par score:\n${summaryMessage}`,
                {
                    title: 'Résultats de l\'analyse',
                    type: 'success',
                    sticky: true
                }
            );
        } catch (error) {
            console.error('Erreur lors de l\'affichage des résultats:', error);
            this.notificationService.add('Impossible d\'afficher les résultats: ' + (error.message || 'Erreur inconnue'), {
                title: 'Erreur',
                type: 'danger',
            });
        }
    }
});