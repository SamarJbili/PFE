# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ApplicantAnalysis(models.Model):
    _name = 'hr.applicant.analysis'
    _description = 'Applicant CV Analysis'

    name = fields.Char('Nom du candidat')
    applicant_id = fields.Many2one('hr.applicant', string='Candidature')
    job_id = fields.Many2one('hr.job', string='Poste')
    experience = fields.Char('Expérience')
    skills = fields.Text('Compétences')
    education = fields.Text('Formation')
    attachment_id = fields.Many2one('ir.attachment', string='CV')
    score = fields.Float('Score', default=0.0)

    @api.depends('skills', 'experience', 'education', 'job_id.requirements')
    def _compute_score(self):
        for record in self:
            # Simple scoring algorithm - can be enhanced
            score = 0.0

            # Add points for experience
            try:
                exp_years = float(record.experience or '0')
                if exp_years > 5:
                    score += 40
                elif exp_years > 3:
                    score += 30
                elif exp_years > 1:
                    score += 20
                else:
                    score += 10
            except:
                pass

            # Add points for skills matches
            if record.skills and record.job_id.requirements:
                job_keywords = [kw.lower().strip() for kw in record.job_id.requirements.split(',')]
                candidate_skills = [skill.lower().strip() for skill in record.skills.split(',')]

                matches = sum(1 for skill in candidate_skills if any(kw in skill for kw in job_keywords))
                score += min(matches * 10, 40)  # Max 40 points for skills

            # Add points for education level (simplified)
            education_keywords = {
                'doctorat': 20,
                'master': 15,
                'licence': 10,
                'bac+': 10,
                'bts': 8,
                'dut': 8,
                'bac': 5
            }

            if record.education:
                edu_score = 0
                for key, value in education_keywords.items():
                    if key in record.education.lower():
                        edu_score = max(edu_score, value)

                score += edu_score

            record.score = min(score, 100)  # Cap at 100