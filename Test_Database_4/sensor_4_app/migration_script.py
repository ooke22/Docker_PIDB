from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["LocalTest"]

def rename_collections():
    # Rename collections
    db["sensor_4_app_waferprocessrelation"].rename("sensor_4_app_sensorprocessrelation")
    db["sensor_4_app_electrode"].rename("sensor_4_app_sensor")
    
def update_image_references():
    # Update the 'electrode' field in the 'image' collection to 'sensor'
    image_collection = db["sensor_4_app_image"]
    image_collection.update_many(
        {}, # Update all documents
        {"$rename": {"electrode": "sensor"}}
    )
    
def migrate_waferprocessrelation():
    # Update references in the renamed SensorProcessRelation collection
    relation_collection = db["sensor_4_app_sensorprocessrelation"]
    relation_collection.update_many(
        {}, # Update all documents
        {"$rename": {"electrode": "sensor"}}
    )
    
def main():
    print("Starting migrations...")
    
    # Step 1: Rename collections
    print("Renaming collections...")
    rename_collections()
    print("collections renamed.")
    
    
    # Step 2: Update field references in the 'image' collection
    print("Updating 'electrode' references in 'image' collection...")
    update_image_references()
    print("Image references updated.")
    
    
    # Step 3: Update field references in the SensorProcessRelation collection
    print("Updating 'electrode' references in 'sensorprocessrelation' collection...")
    migrate_waferprocessrelation()
    print("SensorProcessRelation references updated.")
    
    print("Migration completed successfully!")
    
if __name__ == "__main__":
    main()