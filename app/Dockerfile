# Multi-stage build: real production deploy today is Railway's Nixpacks
# auto-detection (see docs/FLAGSHIP_MARKET_COVERAGE.md), not this
# Dockerfile -- this exists to demonstrate the containerization pattern
# itself (a genuinely common Senior Backend interview topic: "walk me
# through how you'd containerize this service") and to be a real,
# runnable option if a future deploy target requires it.

# --- Build stage -------------------------------------------------------
# Dependencies resolved in their OWN layer (pom.xml copied before src/),
# so a source-only change reuses Docker's cached dependency layer instead
# of re-downloading the full Maven repo on every build -- the real reason
# multi-stage builds are usually also layered internally, not just about
# the final image excluding build tooling.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline

COPY src ./src
# Tests are NOT re-run inside the image build: they already run in CI
# (GitHub Actions, real Testcontainers Postgres/Redis/Kafka) and locally
# -- Testcontainers needs Docker-in-Docker here, real added complexity
# for zero additional signal over what CI already proves. JaCoCo skipped
# for the same "already covered elsewhere" reason (see docs/LESSONS.md
# for why it can also false-fail depending on the builder JDK).
RUN mvn -q -B -DskipTests -Djacoco.skip=true package

# --- Runtime stage -------------------------------------------------------
# JRE, not a full JDK -- the runtime image never compiles anything.
# Alpine keeps the final image small; eclipse-temurin is the actively
# maintained, widely-used OpenJDK distribution (Oracle's own images
# require a commercial license for production use past JDK 17 in some
# configurations -- Temurin has no such ambiguity).
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Real security practice, not boilerplate: without this the container
# runs the app as root, which is a genuinely unnecessary privilege
# escalation surface if the JVM or a dependency is ever compromised --
# the process only needs to read its own jar and bind a port, neither of
# which requires root.
RUN addgroup -S app && adduser -S app -G app
USER app

COPY --from=build /build/target/customer-app-0.0.1-SNAPSHOT.jar app.jar

# Matches application.properties' server.port=${PORT:8080} -- 8080 is
# the real default and what a local `docker run` needs published;
# Railway/most PaaS targets override PORT at runtime regardless.
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
