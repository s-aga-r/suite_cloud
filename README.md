# Suite Cloud

The infrastructure app for [Frappe Suite](https://github.com/frappe/suite): it deploys and manages
the servers Suite's products run on, from a Frappe site. Today that is [Stalwart](https://stalw.art)
mail servers (clusters, servers, DNS records, Ansible-driven deployments), which used to ship inside
Suite's Mail module. Other services Suite depends on, such as Meet's SFU server, are meant to land
here too.

Suite Cloud and Frappe Suite are independent. Install either one alone, or both on the same site;
Suite talks to whichever servers you point it at.

## What it manages today

| DocType | Purpose |
| --- | --- |
| Mail Cluster | A Stalwart cluster: hostname, SSH keypair used to reach its servers, recovery admin, and the data / blob / search / in-memory stores that go into the bootstrap plan |
| Mail Cluster Store, Mail Cluster Store HTTP Auth | Store definitions (RocksDB, PostgreSQL, S3, ElasticSearch, Redis, ...) rendered into Stalwart's bootstrap config |
| Mail Server | A host in a cluster: SSH access, resolved IPs, generated bootstrap NDJSON |
| Server Job | Shell commands run on a server over SSH, with per-command exit codes and output |
| Server Ansible Play, Server Ansible Play Task | Ansible playbook runs (install Docker, deploy Stalwart) tracked task by task |
| Server Deployment | A Stalwart deployment: docker-compose services, env, bootstrap plan; runs the deploy playbook |
| DNS Record | Records under the root domain, pushed to and verified against your DNS provider |
| Mail Directory Account, Mail Directory Email, Mail Directory Group Member | Users and groups with their addresses, aliases and memberships; the tables Stalwart's SQL directory reads (see below) |
| Suite Cloud Settings | Root domain, DNS provider credentials, Stalwart versions, job timeouts |

Playbooks live in `suite_cloud/deploy/playbooks`, the Frappe Cloud helper scripts in `suite_cloud/deploy/fc`.
DNS records, server jobs, Ansible plays and the settings are service-agnostic; only the cluster, server and
deployment DocTypes are Stalwart-specific.

## Install

```sh
bench get-app https://github.com/frappe/suite_cloud
bench --site yoursite install-app suite_cloud
```

`ansible` must be available on the bench host (`apt install ansible`; Frappe Cloud installs it from
`pyproject.toml`). Python dependencies (paramiko, dnspython, dns-lexicon, ansible-runner) come with
the app.

## Settings

`Suite Cloud Settings` (desk: `/app/suite-cloud-settings`) holds:

- **DNS**: root domain name, default TTL, and the DNS provider with its credentials
  (Route53, DigitalOcean, Cloudflare, Hetzner, Linode, Namecheap, GoDaddy). Saving with changed
  credentials reads the zone's MX records once to prove they work.
- **Stalwart**: the Stalwart and Stalwart CLI versions a deployment pins.
- **Timeouts**: background job timeouts for Ansible plays, server jobs and deployments.

Every value can also be set in `site_config.json` under a `suite_cloud` key; settings win when both
are set:

```json
{
  "suite_cloud": {
    "root_domain_name": "example.com",
    "stalwart_version": "v0.16.16"
  }
}
```

## SQL directory

Stalwart can authenticate users and resolve recipients straight from the site's database through
its [SQL directory](https://stalw.art/docs/auth/backend/sql/). `Mail Directory Account` is the
`accounts` table of that setup: the account's email is its login name, passwords are stored as a
SHA-512 crypt hash (what `openssl passwd -6` produces) in the `secret` column, and the `enabled`
flag plays the role of `active`. Its two child tables are the `emails` table (`Mail Directory
Email`, with the primary address kept in sync and aliases such as `@example.org` for a catch-all)
and the `group_members` table (`Mail Directory Group Member`, listing the groups an account belongs
to). Groups are accounts of type `group`; they never get a secret.

Point a Stalwart directory of type `Sql` at the site database with a MySQL store (a read-only
database user with `SELECT` on the three tables is enough) and override the queries so they read
Frappe's tables. MySQL and MariaDB take `?` placeholders; PostgreSQL takes `$1`.

```json
{
  "@type": "Sql",
  "description": "Suite Cloud directory",
  "store": {
    "@type": "MySql",
    "host": "db.example.com",
    "port": 3306,
    "database": "site_db_name",
    "authUsername": "stalwart",
    "authSecret": { "@type": "Value", "secret": "..." }
  },
  "columnEmail": "name",
  "columnSecret": "secret",
  "columnDescription": "description",
  "columnClass": "type",
  "queryLogin": "SELECT `name`, `secret`, `description`, `type` FROM `tabMail Directory Account` WHERE `name` = ? AND `enabled` = 1",
  "queryRecipient": "SELECT a.`name`, a.`secret`, a.`description`, a.`type` FROM `tabMail Directory Account` a JOIN `tabMail Directory Email` e ON e.`parent` = a.`name` WHERE e.`address` = ? AND a.`enabled` = 1 LIMIT 1",
  "queryMemberOf": "SELECT `member_of` FROM `tabMail Directory Group Member` WHERE `parent` = ?",
  "queryEmailAliases": "SELECT `address` FROM `tabMail Directory Email` WHERE `parent` = ? ORDER BY `type` DESC"
}
```

The recipient query joins through the addresses table, so aliases and catch-alls resolve to their
account; the aliases query lists the primary address first.

## Moving from Frappe Suite

Sites that deployed servers through Suite keep their data:

1. Update Frappe Suite and run `bench --site yoursite migrate`. Suite's hand-over patch releases the
   deployment DocTypes: their tables and rows (clusters, SSH keys, servers, job history) stay in the
   database; only the DocType definitions are removed. On sites that never created a cluster or
   server the empty tables are dropped too.
2. `bench --site yoursite install-app suite_cloud`. Installing adopts the existing tables, copies
   the root domain, DNS provider credentials, Stalwart versions and timeouts that Suite's Mail
   Settings used to hold into Suite Cloud Settings, and completes clusters and servers that older
   Suite versions (or a restored standalone mail backup) left without an SSH keypair, recovery
   admin, default domain, recovery port or bootstrap plan.

Installing Suite Cloud before Suite has migrated is refused, since both apps would then define the
same DocTypes.

## Walkthrough

![Cluster](suite_cloud/docs/screenshots/cluster-details.png)
![Server](suite_cloud/docs/screenshots/server-details.png)
![SSH](suite_cloud/docs/screenshots/server-ssh.png)
![Install Stalwart](suite_cloud/docs/screenshots/server-install-stalwart.png)
![Stalwart login](suite_cloud/docs/screenshots/stalwart-login.png)

## License

AGPL-3.0
