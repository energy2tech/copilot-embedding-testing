-- Requires an existing empty destination schema; never rerun INSERTs on populated tables.
CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`customers` (
    `customer_id` INT NOT NULL,
    `customer_name` STRING NOT NULL,
    `industry` STRING NOT NULL,
    `region` STRING NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`plants` (
    `plant_id` INT NOT NULL,
    `plant_name` STRING NOT NULL,
    `region` STRING NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`products` (
    `product_id` INT NOT NULL,
    `sku` STRING NOT NULL,
    `product_name` STRING NOT NULL,
    `unit_price` DECIMAL(12,2) NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`sales_order_lines` (
    `order_line_id` INT NOT NULL,
    `order_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    `ordered_quantity` INT NOT NULL,
    `unit_price` DECIMAL(12,2) NOT NULL,
    `line_amount` DECIMAL(12,2) NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`sales_orders` (
    `order_id` INT NOT NULL,
    `customer_id` INT NOT NULL,
    `order_date` DATE NOT NULL,
    `requested_date` DATE NOT NULL,
    `status` STRING NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`shipment_lines` (
    `shipment_line_id` INT NOT NULL,
    `shipment_id` INT NOT NULL,
    `order_line_id` INT NOT NULL,
    `shipped_quantity` INT NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`shipments` (
    `shipment_id` INT NOT NULL,
    `order_id` INT NOT NULL,
    `ship_date` DATE NOT NULL,
    `delivery_date` DATE NOT NULL
) USING DELTA;

CREATE TABLE `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`work_orders` (
    `work_order_id` INT NOT NULL,
    `order_line_id` INT NOT NULL,
    `plant_id` INT NOT NULL,
    `planned_quantity` INT NOT NULL,
    `produced_quantity` INT NOT NULL,
    `status` STRING NOT NULL
) USING DELTA;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`customers` (`customer_id`, `customer_name`, `industry`, `region`) SELECT `customer_id`, `customer_name`, `industry`, `region` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`customers`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`plants` (`plant_id`, `plant_name`, `region`) SELECT `plant_id`, `plant_name`, `region` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`plants`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`products` (`product_id`, `sku`, `product_name`, `unit_price`) SELECT `product_id`, `sku`, `product_name`, `unit_price` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`products`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`sales_order_lines` (`order_line_id`, `order_id`, `product_id`, `ordered_quantity`, `unit_price`, `line_amount`) SELECT `order_line_id`, `order_id`, `product_id`, `ordered_quantity`, `unit_price`, `line_amount` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`sales_order_lines`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`sales_orders` (`order_id`, `customer_id`, `order_date`, `requested_date`, `status`) SELECT `order_id`, `customer_id`, `order_date`, `requested_date`, `status` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`sales_orders`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`shipment_lines` (`shipment_line_id`, `shipment_id`, `order_line_id`, `shipped_quantity`) SELECT `shipment_line_id`, `shipment_id`, `order_line_id`, `shipped_quantity` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`shipment_lines`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`shipments` (`shipment_id`, `order_id`, `ship_date`, `delivery_date`) SELECT `shipment_id`, `order_id`, `ship_date`, `delivery_date` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`shipments`;

INSERT INTO `dbw_contoso_mfg_demo_eus2`.`manufacturing_managed_demo`.`work_orders` (`work_order_id`, `order_line_id`, `plant_id`, `planned_quantity`, `produced_quantity`, `status`) SELECT `work_order_id`, `order_line_id`, `plant_id`, `planned_quantity`, `produced_quantity`, `status` FROM `contoso_mfg_onelake`.`manufacturing_demo`.`work_orders`;
