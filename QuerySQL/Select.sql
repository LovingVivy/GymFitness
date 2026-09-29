USE gymfitness;

SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'gymfitness';
SELECT COUNT(*) AS trigger_count
FROM information_schema.triggers
WHERE trigger_schema = 'gymfitness';

SELECT COUNT(*) AS foreign_key_count
FROM information_schema.referential_constraints
WHERE constraint_schema = 'gymfitness';

SHOW TRIGGERS FROM gymfitness