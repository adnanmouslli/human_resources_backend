/*
  استعادة درجات KPI المحذوفة بعد مزامنة القوالب بدون id
  المصدر: hr_1_kpi_recovery  (نسخة 2026-10-29)
  الهدف:   hr_1               (إنتاج jana)

  قبل التشغيل:
  1) نسخة احتياطية جديدة ومُتحقَّق منها لـ hr_1
  2) التأكد أن hr_1_kpi_recovery موجودة من نفس الـ bak
  3) تشغيل القسم DRY-RUN أولاً ثم APPLY بعد الموافقة

  الاستراتيجية:
  - مطابقة المعيار أولاً بالاسم داخل نفس template_id
  - وإلا بموقع (section.sort_order + criterion.sort_order)
  - لا نلمس الدرجات الموجودة أصلاً في الإنتاج (مثل 2026-11-16)
  - التقييمات بين 2026-10-29 و 2026-11-15 غير موجودة في النسخة → لا تُستعاد تفاصيلها
*/

USE hr_1;
SET NOCOUNT ON;
SET XACT_ABORT ON;

------------------------------------------------------------
-- 0) خريطة المعايير old_id -> new_id
------------------------------------------------------------
IF OBJECT_ID('tempdb..#crit_map') IS NOT NULL DROP TABLE #crit_map;
CREATE TABLE #crit_map (
  old_id INT NOT NULL PRIMARY KEY,
  new_id INT NOT NULL,
  map_method VARCHAR(20) NOT NULL
);

;WITH old_c AS (
  SELECT c.id AS old_id, c.template_id, LTRIM(RTRIM(c.name)) AS name,
         c.sort_order AS c_ord, s.sort_order AS s_ord
  FROM hr_1_kpi_recovery.dbo.kpi_criteria c
  INNER JOIN hr_1_kpi_recovery.dbo.kpi_sections s ON s.id = c.section_id
),
new_c AS (
  SELECT c.id AS new_id, c.template_id, LTRIM(RTRIM(c.name)) AS name,
         c.sort_order AS c_ord, s.sort_order AS s_ord
  FROM hr_1.dbo.kpi_criteria c
  INNER JOIN hr_1.dbo.kpi_sections s ON s.id = c.section_id
),
by_name AS (
  SELECT o.old_id, MIN(n.new_id) AS new_id
  FROM old_c o
  INNER JOIN new_c n ON n.template_id = o.template_id AND n.name = o.name
  GROUP BY o.old_id
  HAVING COUNT(DISTINCT n.new_id) = 1
)
INSERT INTO #crit_map (old_id, new_id, map_method)
SELECT old_id, new_id, 'name' FROM by_name;

;WITH old_c AS (
  SELECT c.id AS old_id, c.template_id, LTRIM(RTRIM(c.name)) AS name,
         c.sort_order AS c_ord, s.sort_order AS s_ord
  FROM hr_1_kpi_recovery.dbo.kpi_criteria c
  INNER JOIN hr_1_kpi_recovery.dbo.kpi_sections s ON s.id = c.section_id
),
new_c AS (
  SELECT c.id AS new_id, c.template_id, LTRIM(RTRIM(c.name)) AS name,
         c.sort_order AS c_ord, s.sort_order AS s_ord
  FROM hr_1.dbo.kpi_criteria c
  INNER JOIN hr_1.dbo.kpi_sections s ON s.id = c.section_id
),
by_pos AS (
  SELECT o.old_id, MIN(n.new_id) AS new_id
  FROM old_c o
  INNER JOIN new_c n
    ON n.template_id = o.template_id AND n.s_ord = o.s_ord AND n.c_ord = o.c_ord
  WHERE NOT EXISTS (SELECT 1 FROM #crit_map m WHERE m.old_id = o.old_id)
  GROUP BY o.old_id
  HAVING COUNT(DISTINCT n.new_id) = 1
)
INSERT INTO #crit_map (old_id, new_id, map_method)
SELECT old_id, new_id, 'position' FROM by_pos;

------------------------------------------------------------
-- 1) DRY-RUN
------------------------------------------------------------
PRINT '=== DRY-RUN ===';
SELECT map_method, COUNT(*) AS criteria_mapped FROM #crit_map GROUP BY map_method;

SELECT
  COUNT(*) AS candidate_rows,
  COUNT(DISTINCT s.daily_evaluation_id) AS distinct_evals
FROM hr_1_kpi_recovery.dbo.kpi_criterion_scores s
INNER JOIN #crit_map m ON m.old_id = s.criterion_id
INNER JOIN hr_1.dbo.kpi_daily_evaluations e ON e.id = s.daily_evaluation_id
WHERE NOT EXISTS (
  SELECT 1
  FROM hr_1.dbo.kpi_criterion_scores p
  WHERE p.daily_evaluation_id = s.daily_evaluation_id
    AND p.criterion_id = m.new_id
);

SELECT 'prod_scores_before' AS metric, COUNT(*) AS cnt FROM hr_1.dbo.kpi_criterion_scores
UNION ALL
SELECT 'recovery_scores_source', COUNT(*) FROM hr_1_kpi_recovery.dbo.kpi_criterion_scores
UNION ALL
SELECT 'unmapped_old_criteria', COUNT(*)
FROM hr_1_kpi_recovery.dbo.kpi_criteria c
WHERE NOT EXISTS (SELECT 1 FROM #crit_map m WHERE m.old_id = c.id);

-- أوقف هنا للمراجعة. لإتمام الاستعادة: غيّر @DO_APPLY إلى 1
DECLARE @DO_APPLY bit = 0;

IF @DO_APPLY = 0
BEGIN
  PRINT 'Dry-run only. Set @DO_APPLY = 1 to insert.';
  RETURN;
END

------------------------------------------------------------
-- 2) APPLY
------------------------------------------------------------
BEGIN TRAN;

INSERT INTO hr_1.dbo.kpi_criterion_scores
  (daily_evaluation_id, criterion_id, score, max_score, notes, created_at, updated_at)
SELECT
  s.daily_evaluation_id,
  m.new_id,
  s.score,
  s.max_score,
  s.notes,
  s.created_at,
  s.updated_at
FROM hr_1_kpi_recovery.dbo.kpi_criterion_scores s
INNER JOIN #crit_map m ON m.old_id = s.criterion_id
INNER JOIN hr_1.dbo.kpi_daily_evaluations e ON e.id = s.daily_evaluation_id
WHERE NOT EXISTS (
  SELECT 1
  FROM hr_1.dbo.kpi_criterion_scores p
  WHERE p.daily_evaluation_id = s.daily_evaluation_id
    AND p.criterion_id = m.new_id
);

PRINT CONCAT('Inserted rows: ', @@ROWCOUNT);

SELECT 'prod_scores_after' AS metric, COUNT(*) AS cnt FROM hr_1.dbo.kpi_criterion_scores;

-- COMMIT بعد التحقق اليدوي؛ حالياً ROLLBACK آمن إن لم تغيّر السطر التالي
-- COMMIT TRAN;
ROLLBACK TRAN;
PRINT 'Transaction rolled back (safety). Change to COMMIT TRAN after verification.';
