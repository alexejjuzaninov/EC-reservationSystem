FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY pom.xml .
RUN mvn -q dependency:go-offline
COPY src src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /workspace/target/reservation-preview-0.1.0.jar app.jar
USER 10001:10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "app.jar"]
