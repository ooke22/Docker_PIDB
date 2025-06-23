export const processUploadAPI = "http:127.0.0.1.8000/proces_encoder/processes/"

export const processViewsAPI = "https://sensors-test.protonintelligence.io/process/view_processes/"

export const processIdAPI = "https://sensors-test.protonintelligence.io/process/get_processes/"

export const batchEncoderAPI = "https://sensors-test.protonintelligence.io/sensors/electrode-create/"

export const userInfoAPI = 'https://sensors-test.protonintelligence.io/users/user_info/'

export const logoutUserAPI = 'https://sensors-test.protonintelligence.io/users/logout/'

export const electrodeDetailAPI = 'https://sensors-test.protonintelligence.io/sensors/electrode-detail/' 

// Function to generate the full URL for retrieving electrode details
export function retrieveElectrodeAPI(batchLocation, batchId) {
    return `${electrodeDetailAPI}${batchLocation}/${batchId}/`;
}

export const updateElectrodeAPI = 'https://sensors-test.protonintelligence.io/sensors/electrode-update/' 

// Function to generate the full URL for updating electrodes
export function electrodeUpdateUrl(batchLocation, batchId) {
    return `${updateElectrodeAPI}${batchLocation}/${batchId}/`
}

export const batchListAPI = 'https://sensors-test.protonintelligence.io/sensors/v2/batches/'

export const elecImgAPI = 'https://sensors-test.protonintelligence.io/sensors/filtered-elecview-detail/'

export function electrodeURL(batchLocation, batchId, waferID, sensorID) {
    return `${elecImgAPI}${batchLocation}/${batchId}/${waferID}/${sensorID}/`;
}

export const testBatchEncoderAPI = 'https://sensors-test.protonintelligence.io/sensors/electrodes/create/'

export const taskStatusAPI = 'https://sensors-test.protonintelligence.io/sensors/electrodes/taskStatus/'

export const testBatchEncoderAPI2 = 'http://127.0.0.1:8000/test/batch/'
