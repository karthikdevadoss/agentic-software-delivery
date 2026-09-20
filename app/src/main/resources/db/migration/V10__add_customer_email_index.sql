-- No lookup-by-email query existed when V1 created this table, so no
-- index existed either -- a real gap once GET /admin/customers/all
-- (see AdminCustomerController) added sorting/filtering by email at
-- real scale (see loadtest/ for the seeded-volume scenario this
-- supports). Deliberately NOT indexing `name` too: an index isn't
-- free (extra write cost on every insert/update, extra storage), and
-- nothing in this app actually queries by name alone yet -- add it
-- when a real query pattern justifies it, not preemptively.
CREATE INDEX idx_customer_email ON customer (email);
