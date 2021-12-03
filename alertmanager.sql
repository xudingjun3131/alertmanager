CREATE DATABASE IF NOT EXISTS `alertmanager` DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
DROP TABLE IF EXISTS `alertmanager`;
CREATE TABLE `alertmanager` (
  `description` varchar(500) DEFAULT NULL,
  `summary` varchar(500) DEFAULT NULL,
  `valuess` varchar(255) DEFAULT NULL,
  `fingerprint` varchar(255) DEFAULT NULL,
  `startsAt` varchar(255) DEFAULT NULL,
  `endsAt` varchar(255) DEFAULT NULL,
  `updatedAt` varchar(255) DEFAULT NULL,
  `statusss` varchar(255) DEFAULT NULL,
  `generatorURL` varchar(500) DEFAULT NULL,
  `labels` varchar(500) DEFAULT NULL,
  `receivers` varchar(255) DEFAULT NULL,
  UNIQUE KEY `unit_fingerprint_and_stime` (`startsAt`,`fingerprint`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
GRANT ALL ON `alertmanager`.* TO `alertmanager`@"%"  IDENTIFIED BY 'alertmanager';

