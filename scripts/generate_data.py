import os
import random
import pandas as pd
from faker import Faker
from datetime import timedelta


fake = Faker()

# ==========================
# Configuration
# ==========================

NUMBER_OF_INVOICES = 10000
MATCH_RATE = 0.90

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ERP_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "erp",
    "erp_transactions.csv"
)

BANK_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "bank",
    "bank_transactions.csv"
)

RECON_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "reconciliations",
    "reconciliation_results.csv"
)

ANOMALY_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "reconciliations",
    "anomalies.csv"
)


# ==========================
# Data Generation
# ==========================

def generate_data():

    erp_transactions = []
    bank_transactions = []
    reconciliations = []
    anomalies = []


    suppliers = [
        "Microsoft",
        "Oracle",
        "SAP",
        "Dell",
        "HP",
        "Amazon",
        "IBM",
        "Adobe",
        "Google",
        "Cisco"
    ]


    currencies = [
        "EUR",
        "USD",
        "GBP"
    ]


    for i in range(1, NUMBER_OF_INVOICES + 1):

        invoice_id = f"INV{i:05d}"

        invoice_date = fake.date_between(
            start_date="-1y",
            end_date="today"
        )

        due_date = invoice_date + timedelta(days=30)


        amount = round(
            random.uniform(100, 15000),
            2
        )


        currency = random.choice(currencies)

        supplier = random.choice(suppliers)


        erp_transactions.append({

            "invoice_id": invoice_id,
            "supplier": supplier,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "amount": amount,
            "currency": currency,
            "status": "PAID"

        })


        # Decide if transaction is matched

        if random.random() <= MATCH_RATE:

            transaction_id = f"TX{i:05d}"


            bank_transactions.append({

                "transaction_id": transaction_id,
                "transaction_date":
                    invoice_date + timedelta(
                        days=random.randint(0,10)
                    ),

                "description":
                    f"PAYMENT {invoice_id}",

                "amount": amount,

                "currency": currency,

                "reference": invoice_id

            })


            reconciliations.append({

                "invoice_id": invoice_id,

                "transaction_id": transaction_id,

                "status": "MATCHED",

                "difference": 0,

                "matching_method":
                    "REFERENCE_AND_AMOUNT"

            })


        else:

            anomaly_type = random.choice([

                "AMOUNT_MISMATCH",
                "MISSING_PAYMENT",
                "DUPLICATE_PAYMENT",
                "LATE_PAYMENT"

            ])


            transaction_id = f"TX{i:05d}"


            wrong_amount = round(
                amount * random.uniform(
                    0.8,
                    1.2
                ),
                2
            )


            bank_transactions.append({

                "transaction_id":
                    transaction_id,

                "transaction_date":
                    invoice_date + timedelta(
                        days=random.randint(1,60)
                    ),

                "description":
                    f"PAYMENT {invoice_id}",

                "amount":
                    wrong_amount,

                "currency":
                    currency,

                "reference":
                    invoice_id

            })


            difference = round(
                amount - wrong_amount,
                2
            )


            reconciliations.append({

                "invoice_id":
                    invoice_id,

                "transaction_id":
                    transaction_id,

                "status":
                    "FAILED",

                "difference":
                    difference,

                "matching_method":
                    "FAILED"

            })


            anomalies.append({

                "invoice_id":
                    invoice_id,

                "anomaly_type":
                    anomaly_type,

                "severity":
                    random.choice(
                        [
                            "LOW",
                            "MEDIUM",
                            "HIGH"
                        ]
                    ),

                "explanation":
                    f"{anomaly_type.replace('_',' ').lower()} detected for invoice {invoice_id}"

            })


    save_data(
        erp_transactions,
        bank_transactions,
        reconciliations,
        anomalies
    )



def save_data(
        erp,
        bank,
        reconciliations,
        anomalies
):

    pd.DataFrame(erp).to_csv(
        ERP_PATH,
        index=False
    )


    pd.DataFrame(bank).to_csv(
        BANK_PATH,
        index=False
    )


    pd.DataFrame(reconciliations).to_csv(
        RECON_PATH,
        index=False
    )


    pd.DataFrame(anomalies).to_csv(
        ANOMALY_PATH,
        index=False
    )


    print("Dataset generation completed")
    print(f"ERP transactions: {len(erp)}")
    print(f"Bank transactions: {len(bank)}")
    print(f"Reconciliations: {len(reconciliations)}")
    print(f"Anomalies: {len(anomalies)}")



if __name__ == "__main__":
    generate_data()