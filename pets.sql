CREATE DATABASE petsbook;

USE petsbook;

CREATE TABLE pets (
	id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
	name VARCHAR(255) NOT NULL
);

INSERT INTO pets (name) values ("Mel");