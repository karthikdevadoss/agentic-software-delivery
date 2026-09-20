# Microservices Decomposition

Real decisions in `docs/MICROSERVICES_ARCHITECTURE.md`. This directory
is a genuine multi-service decomposition of the same domain `app/` (the
monolithic Customer App) already models — built **alongside** it, not
replacing it. `app/` stays exactly as-is: live, deployed, CI-verified.

| Service | Port | Status |
|---|---|---|
| `eureka-server` | 8761 | Scaffolded, compiles |
| `api-gateway` | 8080 | Scaffolded, compiles, real routing logic wired |
| `customer-service` | 8081 | Scaffolded, compiles — business logic in progress |
| `billing-service` | 8082 | Scaffolded, compiles — business logic in progress |
| `notification-service` | 8083 | Scaffolded, compiles — business logic in progress |
| `metering-service` | 8084 | Scaffolded, compiles — business logic in progress |

Each is a fully independent Spring Boot Maven project — its own
`pom.xml`, own `mvnw`, own database (H2 locally). Not deployed anywhere
yet; commit/push + CI only, per standing instruction.

## Run locally (once business logic lands)

Start in this order (each needs the previous to be up):
```
services/eureka-server    -> ./mvnw spring-boot:run
services/customer-service -> ./mvnw spring-boot:run
services/billing-service, notification-service, metering-service -> ./mvnw spring-boot:run
services/api-gateway      -> ./mvnw spring-boot:run
```
Eureka dashboard: http://localhost:8761
