\# Engineering notes: PatentPath



\## D03 - PostgreSQL



\### Migrations (upgrade, downgrade, upgrade)



```text

downgrade -1: 1190a664399b -> 9422b52fab0b

current after downgrade: 9422b52fab0b

upgrade head: 9422b52fab0b -> 1190a664399b

final current: 1190a664399b (head)



Migration history:

9422b52fab0b -> 1190a664399b (head), add gin index on metadata

<base> -> 9422b52fab0b, create documents and pages tables

```



\### The loader is idempotent



```text

run 1: records=20 inserted=0 updated=0 unchanged=20

run 2: records=20 inserted=0 updated=0 unchanged=20

run 3: Not performed (sample data was not modified)

```



\### EXPLAIN for ?section=7, 54, 135



```text

\-- 1) Planner chooses:

Seq Scan on documents

Execution Time: 0.839 ms



\-- 2) Seq scan disabled:

Bitmap Heap Scan on documents

&#x20; -> Bitmap Index Scan on ix\_documents\_metadata\_gin

Execution Time: 2.024 ms

```



\*\*Why did the planner choose a Seq Scan?\*\*



The table contains only 20 rows, so scanning the entire table is cheaper than using the GIN index.



\*\*When would it switch to the GIN index?\*\*



When the table grows and using the GIN index becomes cheaper than scanning the entire table.
